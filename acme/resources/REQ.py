#
#	REQ.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	ResourceType: Request
#

from typing import Dict, Any
from Constants import Constants as C
from Types import ResourceTypes as T, Result, RequestArguments, RequestHeaders, Operation, RequestStatus, CSERequest
from Validator import constructPolicy, addPolicy
import Utils
from .Resource import *
from .AnnounceableResource import AnnounceableResource
from Configuration import Configuration



# Attribute policies for this resource are constructed during startup of the CSE
attributePolicies = constructPolicy([ 
	'ty', 'ri', 'rn', 'pi', 'acpi', 'ct', 'lt', 'et', 'lbl', 'daci', 
])
reqPolicies = constructPolicy([
	'op', 'tg', 'org', 'rid', 'mi', 'pc', 'rs', 'ors'
])
attributePolicies = addPolicy(attributePolicies, reqPolicies)



class REQ(Resource):

	def __init__(self, jsn:dict=None, pi:str=None, create:bool=False) -> None:
		super().__init__(T.REQ, jsn, pi, create=create, attributePolicies=attributePolicies)


	# Enable check for allowed sub-resources
	def canHaveChild(self, resource:Resource) -> bool:
		return super()._canHaveChild(resource, [ T.SUB ])


	@staticmethod
	def createRequestResource(request:CSERequest) -> Result:
		"""	Create an initialized <request> resource.
		"""
		
		# calculate request et
		minEt = Utils.getResourceDate(Configuration.get('cse.req.minet'))
		maxEt = Utils.getResourceDate(Configuration.get('cse.req.maxet'))
		if request.args.rpts is not None:
			et = request.args.rpts if request.args.rpts < maxEt else maxEt
		else:
			et = minEt

		jsn:Dict[str, Any] = {
			'm2m:req' : {
				'et'	: et,
				'lbl'	: [ request.headers.originator ],
				'op'	: request.args.operation,
				'tg'	: request.id,
				'org'	: request.headers.originator,
				'rid'	: request.headers.requestIdentifier,
				'mi'	: {
					'ty'	: request.headers.resourceType,
					'ot'	: Utils.getResourceDate(),
					'rqet'	: request.headers.requestExpirationTimestamp,
					'rset'	: request.headers.responseExpirationTimestamp,
					'rt'	: { 
						'rtv' : request.args.rt
					},
					'rp'	: request.args.rp,
					'rcn'	: request.args.rcn,
					'fc'	: {
						'fu'	: request.args.fu,
						'fo'	: request.args.fo,
					},
					'drt'	: request.args.drt,
					'rvi'	: request.headers.releaseVersionIndicator if request.headers.releaseVersionIndicator is not None else C.hfvRVI,
				},
				'rs'	: RequestStatus.PENDING,
				'ors'	: {
				}
		}}

		# add handlings, conditions and attributes from filter
		for k,v in { **request.args.handling, **request.args.conditions, **request.args.attributes}.items():
			Utils.setXPath(jsn, 'm2m:req/mi/fc/%s' % k, v, True)

		# add content
		if request.json is not None and len(request.json) > 0:
			Utils.setXPath(jsn, 'm2m:req/pc', request.json, True)

		# calculate and assign rtu for rt
		if (rtu := request.headers.responseTypeNUs) is not None and len(rtu) > 0:
			Utils.setXPath(jsn, 'm2m:req/mi/rt/nu', [ u for u in rtu if len(u) > 0] )

		if (cseres := Utils.getCSE()).resource is None:
			return Result(rsc=RC.badRequest, dbg=cseres.dbg)
		return Utils.resourceFromJSON(jsn, pi=cseres.resource.ri, ty=T.REQ)


