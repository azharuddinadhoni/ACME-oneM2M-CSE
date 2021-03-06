#
#	NYCFC.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: mgmtObj:myCertFileCred from TS-0022
#

from .MgmtObj import *
from Types import ResourceTypes as T
from Validator import constructPolicy, addPolicy
import Utils

# Attribute policies for this resource are constructed during startup of the CSE
fwrPolicies = constructPolicy([
	'suids', 'mcff', 'mcfc'
])
attributePolicies =  addPolicy(mgmtObjAttributePolicies, fwrPolicies)




class NYCFC(MgmtObj):

	def __init__(self, jsn: dict = None, pi: str = None, create: bool = False) -> None:
		self.resourceAttributePolicies = fwrPolicies	# only the resource type's own policies
		super().__init__(jsn, pi, mgd=T.NYCFC, create=create, attributePolicies=attributePolicies)

