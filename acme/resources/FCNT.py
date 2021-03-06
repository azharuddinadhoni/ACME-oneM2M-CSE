#
#	FCNT.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: FlexContainer
#

import sys
from typing import List
from Constants import Constants as C
from Types import ResourceTypes as T, Result, ResponseCode as RC
from Validator import constructPolicy, addPolicy
import Utils
from .Resource import *
from .AnnounceableResource import AnnounceableResource
import functools 




# Attribute policies for this resource are constructed during startup of the CSE
attributePolicies = constructPolicy([ 
	'ty', 'ri', 'rn', 'pi', 'acpi', 'ct', 'lt', 'et', 'st', 'lbl', 'at', 'aa', 'cr', 'daci', 'loc',
])
fcntPolicies = constructPolicy([
	'cnd', 'or', 'cs', 'nl', 'mni', 'mia', 'mbs', 'cni', 'dgt'
])
attributePolicies = addPolicy(attributePolicies, fcntPolicies)


class FCNT(AnnounceableResource):

	def __init__(self, jsn:dict=None, pi:str=None, fcntType:str=None, create:bool=False) -> None:
		super().__init__(T.FCNT, jsn, pi, tpe=fcntType, create=create, attributePolicies=attributePolicies)

		self.resourceAttributePolicies = fcntPolicies	# only the resource type's own policies

		if self.json is not None:
			self.setAttribute('cs', 0, overwrite=False)

			# "current" attributes are added when necessary in the validate() method

			# Indicates whether this FC has flexContainerInstances. 
			# Might change during the lifetime of a resource. Used for optimization
			self.hasInstances = False

		self.ignoreAttributes = self.internalAttributes + [ 'acpi', 'cbs', 'cni', 'cnd', 'cs', 'cr', 'ct', 'et', 'lt', 'mbs', 'mia', 'mni', 'or', 'pi', 'ri', 'rn', 'st', 'ty', 'at' ]


	# Enable check for allowed sub-resources
	def canHaveChild(self, resource:Resource) -> bool:
		return super()._canHaveChild(resource,	
									 [ T.CNT,
									   T.FCNT,
									   T.SUB
									   # FlexContainerInstances are added by the flexContainer itself
									 ])


	def activate(self, parentResource:Resource, originator:str) -> Result:
		if not (res := super().activate(parentResource, originator)).status:
			return res

		# register latest and oldest virtual resources
		Logging.logDebug('Registering latest and oldest virtual resources for: %s' % self.ri)

		if self.hasInstances:
			# add latest
			resource = Utils.resourceFromJSON({}, pi=self.ri, acpi=self.acpi, ty=T.FCNT_LA).resource
			if (res := CSE.dispatcher.createResource(resource)).resource is None:
				return Result(status=False, rsc=res.rsc, dbg=res.dbg)

			# add oldest
			resource = Utils.resourceFromJSON({}, pi=self.ri, acpi=self.acpi, ty=T.FCNT_OL).resource
			if (res := CSE.dispatcher.createResource(resource)).resource is None:
				return Result(status=False, rsc=res.rsc, dbg=res.dbg)
		return Result(status=True)


	# This method is NOT called when adding FCIN!!

	def childWillBeAdded(self, childResource:Resource, originator:str) -> Result:
		if not (res := super().childWillBeAdded(childResource, originator)).status:
			return res

		# Check whether the child's rn is "ol" or "la".
		if (rn := childResource['rn']) is not None and rn in ['ol', 'la']:
			return Result(status=False, rsc=RC.operationNotAllowed, dbg='resource types "latest" or "oldest" cannot be added')
	
		return Result(status=True)


	# Handle the removal of a FCIN. 
	def childRemoved(self, childResource:Resource, originator:str) -> None:
		super().childRemoved(childResource, originator)
		if childResource.ty == T.FCI:	# Validate if child was FCIN
			self._validateChildren(originator, deletingFCI=True)


	# Checking the presence of cnd and calculating the size
	def validate(self, originator:str=None, create:bool=False) -> Result:
		if not (res := super().validate(originator, create)).status:
			return res
		return self._validateChildren(originator)

		# No CND? -> Validator
		# if (cnd := self.cnd) is None or len(cnd) == 0:
		# 	return Result(status=False, rsc=RC.contentsUnacceptable, dbg='cnd attribute missing or empty')


	def _validateChildren(self, originator:str, deletingFCI:bool=False) -> Result:
		""" Internal validation and checks. This called more often then just from
			the validate() method, for example when deleting a FCIN.
		"""
		# Calculate contentSize
		# This is not at all realistic since this is the in-memory representation
		# TODO better implementation needed 
		cs = 0
		for attr in self.json:
			if attr in self.ignoreAttributes:
				continue
			cs += sys.getsizeof(self[attr])
		self['cs'] = cs

		#
		#	Handle flexContainerInstances
		#

		# TODO When cni and cbs is set to 0, then delete mni, mbs, la, ol, and all children
		

		if self.mni is not None or self.mbs is not None or self.mia is not None: # not when this method is called when already deleting a child resource
			self.hasInstances = True	# Change the internal flag whether this FC has flexContainerInstances

			if not deletingFCI:
				self.addFlexContainerInstance(originator)
			
			fci = self.flexContainerInstances()
			fcii = len(fci)	# number of instances

			# check mni
			if self.mni is not None:
				mni = self.mni
				i = 0
				l = fcii
				while fcii > mni and i < l:
					# remove oldest
					CSE.dispatcher.deleteResource(fci[i])
					fcii -= 1
					i += 1
					changed = True

				# Add "current" atribute, if it is not there
				self.setAttribute('cni', 0, overwrite=False)
				fci = self.flexContainerInstances()	# get FCIs again (bc may be different now)
				fcii = len(fci)

			# Always assign cni. Might have changed above
			self['cni'] = fcii 
			
			# Calculate cbs
			cbs = 0
			for f in fci:					
				cbs += f.cs

			# check size
			if self.mbs is not None:
				mbs = self.mbs
				i = 0
				#l = len(fci)
				while cbs > mbs and i < fcii:
					# remove oldest
					cbs -= fci[i].cs			
					CSE.dispatcher.deleteResource(fci[i])
					i += 1

				# Add "current" atribute, if it is not there
				self.setAttribute('cbs', 0, overwrite=False)
			
			# Always assign cbs. Might have changed above
			self['cbs'] = cbs

		# TODO Remove la, ol, existing FCI when mni etc are not present anymore.

		
		# May have been changed, so store the resource
		self.dbUpdate()
		return Result(status=True)


	# Get all flexContainerInstances of a resource and return a sorted (by ct) list 
	def flexContainerInstances(self) -> List[Resource]:
		return sorted(CSE.dispatcher.directChildResources(self.ri, T.FCI), key=lambda x: (x.ct))


	# Add a new FlexContainerInstance for this flexContainer
	def addFlexContainerInstance(self, originator:str) -> None:
		Logging.logDebug('Adding flexContainerInstance')
		jsn:Dict[str, Any] = {	'rn'  : '%s_%d' % (self.rn, self.st), }
		if self.lbl is not None:
			jsn['lbl'] = self.lbl

		for attr in self.json:
			if attr not in self.ignoreAttributes:
				jsn[attr] = self[attr]
				continue
			# special for at attribute. It might contain additional id's when it
			# is announced. Those we don't want to copy.
			if attr == 'at':
				jsn['at'] = [ x for x in self['at'] if x.count('/') == 1 ]	# Only copy single csi in at

		resource = Utils.resourceFromJSON(jsn={ self.tpe : jsn }, pi=self.ri, acpi=self.acpi, ty=T.FCI).resource
		CSE.dispatcher.createResource(resource)
		resource['cs'] = self.cs

		# Check for mia handling
		if self.mia is not None:
			# Take either mia or the maxExpirationDelta, whatever is smaller
			maxEt = Utils.getResourceDate(self.mia if self.mia <= (med := Configuration.get('cse.maxExpirationDelta')) else med)
			# Only replace the childresource's et if it is greater than the calculated maxEt
			if resource.et > maxEt:
				resource.setAttribute('et', maxEt)

		resource.dbUpdate()	# store


