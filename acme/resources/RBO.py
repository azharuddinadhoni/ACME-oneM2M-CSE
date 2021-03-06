#
#	RBO.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: mgmtObj:Reboot
#

from .MgmtObj import *
from Types import ResourceTypes as T, ResponseCode as RC
from Validator import constructPolicy, addPolicy
import Utils

# Attribute policies for this resource are constructed during startup of the CSE
rboPolicies = constructPolicy([
	'rbo', 'far'
])
attributePolicies =  addPolicy(mgmtObjAttributePolicies, rboPolicies)


class RBO(MgmtObj):

	def __init__(self, jsn: dict = None, pi: str = None, create: bool = False) -> None:
		self.resourceAttributePolicies = rboPolicies	# only the resource type's own policies
		super().__init__(jsn, pi, mgd=T.RBO, create=create, attributePolicies=attributePolicies)

		if self.json is not None:
			self.setAttribute('rbo', False, overwrite=True)	# always False
			self.setAttribute('far', False, overwrite=True)	# always False


	#
	#	Handling the special behaviour for rbo and far attributes in 
	#	validate() and update()
	#

	def validate(self, originator: str = None, create: bool = False) -> Result:
		if not (res := super().validate(originator, create)).status:
			return res
		self.setAttribute('rbo', False, overwrite=True)	# always set (back) to True
		self.setAttribute('far', False, overwrite=True)	# always set (back) to True
		return Result(status=True)


	def update(self, jsn:dict=None, originator:str=None) -> Result:
		# Check for rbo & far updates 
		if jsn is not None and self.tpe in jsn:
			rbo = Utils.findXPath(jsn, 'm2m:rbo/rbo')
			far = Utils.findXPath(jsn, 'm2m:rbo/far')
			if rbo is not None and far is not None and rbo and far:
				return Result(status=False, rsc=RC.badRequest, dbg='update both rbo and far to True is not allowed')

		return super().update(jsn, originator)
