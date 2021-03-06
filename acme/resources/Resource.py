#
#	Resource.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	Base class for all resources
#

# The following import allows to use "Resource" inside a method typing definition
from __future__ import annotations
from typing import Any, Tuple, Union, Dict, List
from Logging import Logging
from Constants import Constants as C
from Types import ResourceTypes as T, Result, NotificationEventType, ResponseCode as RC
from Configuration import Configuration
import Utils, CSE
import datetime, random, traceback
from .Resource import *

# Future TODO: Check RO/WO etc for attributes (list of attributes per resource?)



class Resource(object):
	_rtype 				= '__rtype__'
	_srn				= '__srn__'
	_node				= '__node__'
	_createdInternally	= '__createdInternally__'	# TODO better name. This is actually an RI
	_imported			= '__imported__'
	_isVirtual 			= '__isVirtual__'
	_announcedTo 		= '__announcedTo__'			# List
	_isInstantiated		= '__isInstantiated__'
	_originator			= '__originator__'
	_modified			= '__modified__'

	# ATTN: There is a similar definition in FCNT! Don't Forget to add attributes there as well
	internalAttributes	= [ _rtype, _srn, _node, _createdInternally, _imported, _isVirtual, _isInstantiated, _originator, _announcedTo, _modified ]

	def __init__(self, ty:Union[T, int], jsn:dict=None, pi:str=None, tpe:str=None, create:bool=False, inheritACP:bool=False, readOnly:bool=False, rn:str=None, attributePolicies:dict=None, isVirtual:bool=False) -> None:
		self.tpe = tpe
		if isinstance(ty, T) and ty not in [ T.FCNT, T.FCI ]: 	# For some types the tpe/root is empty and will be set later in this method
			self.tpe = ty.tpe() if tpe is None else tpe
		self.readOnly = readOnly
		self.inheritACP = inheritACP
		self.json = {}
		self.attributePolicies = attributePolicies

		if jsn is not None: 
			self.isImported = jsn.get(C.jsnIsImported)
			if self.tpe in jsn:
				self.json = jsn[self.tpe].copy()
			else:
				self.json = jsn.copy()
			self._originalJson = jsn.copy()	# keep for validation later
		else:
			# no JSON, so the resource is instantiated programmatically
			self.setAttribute(self._isInstantiated, True)


		if self.json is not None:
			if self.tpe is None: # and _rtype in self:
				self.tpe = self.__rtype__
			self.setAttribute('ri', Utils.uniqueRI(self.tpe), overwrite=False)

			# override rn if given
			if rn is not None:
				self.setAttribute('rn', rn, overwrite=True)
	
			# Check uniqueness of ri. otherwise generate a new one. Only when creating
			# TODO: could be a BAD REQUEST?
			if create:
				while Utils.isUniqueRI(ri := self.attribute('ri')) == False:
					Logging.logWarn("RI: %s is already assigned. Generating new RI." % ri)
					self.setAttribute('ri', Utils.uniqueRI(self.tpe), overwrite=True)

			# Indicate whether this is a virtual resource
			if isVirtual:
				self.setAttribute(self._isVirtual, isVirtual)
	
			# Create an RN if there is none
			self.setAttribute('rn', Utils.uniqueRN(self.tpe), overwrite=False)
			
			# Set some more attributes
			ts = Utils.getResourceDate()
			self.setAttribute('ct', ts, overwrite=False)
			self.setAttribute('lt', ts, overwrite=False)
			if self.ty not in [ T.CSEBase ]:
				self.setAttribute('et', Utils.getResourceDate(Configuration.get('cse.expirationDelta')), overwrite=False) 
			if pi is not None:
				# self.setAttribute('pi', pi, overwrite=False)
				self.setAttribute('pi', pi, overwrite=True)
			if ty is not None:
				if ty in C.stateTagResourceTypes:	# Only for allowed resources
					self.setAttribute('st', 0, overwrite=False)
				self.setAttribute('ty', int(ty))

			#
			## Note: ACPI is set in activate()
			#

			# Remove empty / null attributes from json
			# But see also the comment in update() !!!
			#self.json = {k: v for (k, v) in self.json.items() if v is not None }
			self.json = Utils.deleteNoneValuesFromJSON(self.json)
			# determine and add the srn
			self[self._srn] = Utils.structuredPath(self)
			self[self._rtype] = self.tpe
			self.setAttribute(self._announcedTo, [], overwrite=False)



	# Default encoding implementation. Overwrite in subclasses
	def asJSON(self, embedded: bool = True, update: bool = False, noACP: bool = False) -> dict:
		# remove (from a copy) all internal attributes before printing
		jsn = self.json.copy()
		for k in self.internalAttributes:
			if k in jsn: 
				del jsn[k]

		if noACP:
			if 'acpi' in jsn:
				del jsn['acpi']
		if update:
			for k in [ 'ri', 'ty', 'pi', 'ct', 'lt', 'st', 'rn', 'mgd']:
				jsn.pop(k, None) # instead of using "del jsn[k]" this doesn't throw an exception if k doesn't exist

		return { self.tpe : jsn } if embedded else jsn


	# This method is called to to activate a resource. This is not always the
	# case, e.g. when a resource object is just used temporarly.
	# NO notification on activation/creation!
	# Implemented in sub-classes.
	# Note: CR and ACPI are set in RegistrationManager
	def activate(self, parentResource: Resource, originator: str) -> Result:
		Logging.logDebug('Activating resource: %s' % self.ri)

		# validate the attributes but only when the resource is not instantiated.
		# We assume that an instantiated resource is always correct
		# Also don't validate virtual resources
		if (self[self._isInstantiated] is None or not self[self._isInstantiated]) and not self[self._isVirtual] :
			if not (res := CSE.validator.validateAttributes(self._originalJson, self.tpe, self.attributePolicies, isImported=self.isImported, createdInternally=self.isCreatedInternally())).status:
				return res

		# validate the resource logic
		if not (res := self.validate(originator, create=True)).status:
			return res

		# increment parent resource's state tag
		if parentResource is not None and parentResource.st is not None:
			parentResource = parentResource.dbReload().resource	# Read the resource again in case it was updated in the DB
			parentResource['st'] = parentResource.st + 1
			if (res := parentResource.dbUpdate()).resource is None:
				return Result(status=False, rsc=res.rsc, dbg=res.dbg)

		self.setAttribute(self._originator, originator, overwrite=False)
		self.setAttribute(self._rtype, self.tpe, overwrite=False) 

		return Result(status=True, rsc=RC.OK)


	# Deactivate an active resource.
	# Send notification on deletion
	def deactivate(self, originator:str) -> None:
		Logging.logDebug('Deactivating and removing sub-resources: %s' % self.ri)
		# First check notification because the subscription will be removed
		# when the subresources are removed
		CSE.notification.checkSubscriptions(self, NotificationEventType.resourceDelete)
		
		# Remove directChildResources
		rs = CSE.dispatcher.directChildResources(self.ri)
		for r in rs:
			self.childRemoved(r, originator)
			CSE.dispatcher.deleteResource(r, originator)


	# Update this resource with (new) fields.
	# Call validate() afterward to react on changes.
	def update(self, jsn:dict=None, originator:str=None) -> Result:
		jsonOrg = self.json.copy()	# Save for later for notification

		j = None
		if jsn is not None:
			if self.tpe not in jsn and self.ty not in [T.FCNTAnnc, T.FCIAnnc]:	# Don't check announced versions of announced FCNT
				Logging.logWarn("Update types don't match")
				return Result(status=False, rsc=RC.contentsUnacceptable, dbg='resource types mismatch')

			# validate the attributes
			if not (res := CSE.validator.validateAttributes(jsn, self.tpe, self.attributePolicies, create=False, createdInternally=self.isCreatedInternally())).status:
				return res

			if self.ty not in [T.FCNTAnnc, T.FCIAnnc]:
				j = jsn[self.tpe] # get structure under the resource type specifier
			else:
				j = Utils.findXPath(jsn, '{0}')
			for key in j:
				# Leave out some attributes
				if key in ['ct', 'lt', 'pi', 'ri', 'rn', 'st', 'ty']:
					continue
				value = j[key]

				# Special handling for et when deleted/set to Null: set a new et
				if key == 'et' and value is None:
					self['et'] = Utils.getResourceDate(Configuration.get('cse.expirationDelta'))
					continue
				self.setAttribute(key, value, overwrite=True) # copy new value or add new attributes

		# - state and lt
		if 'st' in self.json:	# Update the state
			self['st'] += 1
		if 'lt' in self.json:	# Update the lastModifiedTime
			self['lt'] = Utils.getResourceDate()

		# Remove empty / null attributes from json
		# 2020-08-10 : 	TinyDB doesn't overwrite the whole document but makes an attribute-by-attribute 
		#				update. That means that removed attributes are NOT removed. There is now a 
		#				procedure in the Storage component that removes nulled attributes as well.
		#self.json = {k: v for (k, v) in self.json.items() if v is not None }

		# Do some extra validations, if necessary
		if not (res := self.validate(originator)).status:
			return res

		# store last modified attributes
		self[self._modified] = Utils.resourceDiff(jsonOrg, self.json, j)

		# Check subscriptions
		CSE.notification.checkSubscriptions(self, NotificationEventType.resourceUpdate, modifiedAttributes=self[self._modified])

		return Result(status=True)


	def childWillBeAdded(self, childResource:Resource, originator:str) -> Result:
		""" Called before a child will be added to a resource.
			This method return True, or False in kind the adding should be rejected, and an error code."""
		return Result(status=True)


	def childAdded(self, childResource:Resource, originator:str) -> None:
		""" Called when a child resource was added to the resource. """
		CSE.notification.checkSubscriptions(self, NotificationEventType.createDirectChild, childResource)


	def childRemoved(self, childResource:Resource, originator:str) -> None:
		""" Call when child resource was removed from the resource. """
		CSE.notification.checkSubscriptions(self, NotificationEventType.deleteDirectChild, childResource)


	def canHaveChild(self, resource:Resource) -> bool:
		""" MUST be implemented by each class."""
		raise NotImplementedError('canHaveChild()')


	def _canHaveChild(self, resource:Resource, allowedChildResourceTypes:list) -> bool:
		""" It checks whether a fresource may have a certain child resources. This is called from child class. """
		from .Unknown import Unknown # Unknown imports this class, therefore import only here
		return resource['ty'] in allowedChildResourceTypes or isinstance(resource, Unknown)


	def validate(self, originator:str=None, create:bool=False) -> Result:
		""" Validate a resource. Usually called within activate() or update() methods. """
		Logging.logDebug('Validating resource: %s' % self.ri)
		if (not Utils.isValidID(self.ri) or
			not Utils.isValidID(self.pi) or
			not Utils.isValidID(self.rn)):
			err = 'Invalid ID ri: %s, pi: %s, rn: %s)' % (self.ri, self.pi, self.rn)
			Logging.logDebug(err)
			return Result(status=False, rsc=RC.contentsUnacceptable, dbg=err)

		# expirationTime handling
		if (et := self.et) is not None:
			if self.ty == T.CSEBase:
				err = 'expirationTime is not allowed in CSEBase'
				Logging.logWarn(err)
				return Result(status=False, rsc=RC.badRequest, dbg=err)
			if len(et) > 0 and et < (etNow := Utils.getResourceDate()):
				err = 'expirationTime is in the past: %s < %s' % (et, etNow)
				Logging.logWarn(err)
				return Result(status=False, rsc=RC.badRequest, dbg=err)
			if et > (etMax := Utils.getResourceDate(Configuration.get('cse.maxExpirationDelta'))):
				Logging.logDebug('Correcting expirationDate to maxExpiration: %s -> %s' % (et, etMax))
				self['et'] = etMax
		return Result(status=True)


	def createAnnouncedJSON(self) -> Tuple[dict, int, str]:
		"""	Create an announceable resource. This method is implemented by the
			resource implementations that support announceable versions.
		"""
		return None, RC.badRequest, 'wrong resource type or announcement not supported'

	#########################################################################

	def createdInternally(self) -> str:
		""" Return the resource.ri for which this ACP was created, or None. """
		return self[self._createdInternally]


	def isCreatedInternally(self) -> bool:
		""" Return the resource.ri for which this resource was created, or None. """
		return self[self._createdInternally] is not None

	def setCreatedInternally(self, value:str) -> None:
		"""	Save the RI for which this resource was created for. This has some
			impacts on internal handling and checks.
		"""
		self[self._createdInternally] = value


	#########################################################################

	#
	#	Attribute handling
	#


	def setAttribute(self, key:str, value:Any, overwrite:bool=True) -> None:
		Utils.setXPath(self.json, key, value, overwrite)


	def attribute(self, key:str, default:Any=None) -> Any:
		if '/' in key:	# search in path
			return Utils.findXPath(self.json, key, default)
		if self.hasAttribute(key):
			return self.json[key]
		return default


	def hasAttribute(self, key: str) -> bool:
		# TODO check sub-elements as well
		return key in self.json


	def delAttribute(self, key: str, setNone: bool = True) -> None:
		""" Delete the attribute 'key' from the resource. By default the attribute
			is not deleted but set to 'None' and are removed correctly in the 
			DB later. If 'setNone' is False, then the attribute 'key' is 
			really deleted from the resource.
		"""
		if self.hasAttribute(key):
			if setNone:
				self.json[key] = None
			else:
				del self.json[key]


	def __setitem__(self, key: str, value: Any) -> None:
		self.setAttribute(key, value)


	def __getitem__(self, key: str) -> Any:
		return self.attribute(key)

	def __delitem__(self, key: str) -> None:
		self.delAttribute(key)


	def __contains__(self, key: str) -> bool:
		return self.hasAttribute(key)

	def __getattr__(self, key: str) -> Any:
		return self.attribute(key)


	#########################################################################

	#
	#	Attribute specific helpers
	#

	def normalizeURIAttribute(self, attributeName: str) -> None:
		""" Normalie the URLs in the poa, nu etc. """
		if (attribute := self[attributeName]) is not None:
			if isinstance(attribute, list):	# list of uris
				result = []
				for uri in attribute:
					result.append(Utils.normalizeURL(uri))
				self[attributeName] = result
			else: 							# single uri
				self[attributeName] = Utils.normalizeURL(attribute)


	#########################################################################

	#
	#	Database functions
	#

	def dbDelete(self) -> Result:
		""" Delete the Resource from the database. """
		return CSE.storage.deleteResource(self)


	def dbUpdate(self) -> Result:
		""" Update the Resource in the database. """
		return CSE.storage.updateResource(self)


	def dbCreate(self, overwrite: bool = False) -> Result:
		return CSE.storage.createResource(self, overwrite)


	def dbReload(self) -> Result:
		"""  Load a new copy from the database. The current resource is NOT changed. """
		return CSE.storage.retrieveResource(ri=self.ri)



	#########################################################################

	#
	#	Misc utilities
	#

	def __str__(self) -> str:
		""" String representation. """
		return str(self.asJSON())


	def __repr__(self) -> str:
		""" Object representation as string. """
		return '%s(ri=%s)' % (self.tpe, self.ri)


	def __eq__(self, other: object) -> bool:
		return isinstance(other, Resource) and self.ri == other.ri


	def isModifiedSince(self, otherResource: Resource) -> bool:
		return self.lt > otherResource.lt


	def retrieveParentResource(self) -> Resource:
		return CSE.dispatcher.retrieveResource(self.pi).resource

