#
#	testAddressing.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	Unit tests for addressing methods
#

import unittest, sys
sys.path.append('../acme')
from Constants import Constants as C
from Types import ResourceTypes as T, ResponseCode as RC
from init import *

# The following code must be executed before anything else because it influences
# the collection of skipped tests.
# It checks whether there actually is a CSE running.
noCSE = not connectionPossible(cseURL)

class TestAddressing(unittest.TestCase):

	@classmethod
	@unittest.skipIf(noCSE, 'No CSEBase')
	def setUpClass(cls):
		cls.cse, rsc = RETRIEVE(cseURL, ORIGINATOR)
		assert rsc == RC.OK, 'Cannot retrieve CSEBase: %s' % cseURL

		jsn = 	{ 'm2m:ae' : {
					'rn'  : aeRN, 
					'api' : 'NMyApp1Id',
				 	'rr'  : False,
				 	'srv' : [ '3' ]
				}}
		cls.ae, rsc = CREATE(cseURL, 'C', T.AE, jsn)	# AE to work under
		assert rsc == RC.created, 'cannot create parent AE'
		cls.originator = findXPath(cls.ae, 'm2m:ae/aei')
		jsn = 	{ 'm2m:cnt' : { 
					'rn'  : cntRN
				}}
		cls.cnt, rsc = CREATE(aeURL, cls.originator, T.CNT, jsn)
		assert rsc == RC.created, 'cannot create container'
		cls.cntRI = findXPath(cls.cnt, 'm2m:cnt/ri')


	@classmethod
	@unittest.skipIf(noCSE, 'No CSEBase')
	def tearDownClass(cls):
		DELETE(aeURL, ORIGINATOR)	# Just delete the AE and everything below it. Ignore whether it exists or not


	@unittest.skipIf(noCSE, 'No CSEBase')
	def test_cseRelativeStructured(self):
		url = '%s%s/%s/%s' % (URL, CSERN, aeRN, cntRN)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)
		url = '%s-/%s/%s' % (URL, aeRN, cntRN)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)


	@unittest.skipIf(noCSE, 'No CSEBase')
	def test_cseRelativeUnstructured(self):
		url = '%s%s' % (URL, TestAddressing.cntRI)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)


	@unittest.skipIf(noCSE, 'No CSEBase')
	def test_spRelativeStructured(self):
		url = '%s~%s/%s/%s/%s' % (URL, CSEID, CSERN, aeRN, cntRN)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)
		url = '%s~%s/-/%s/%s' % (URL, CSEID, aeRN, cntRN)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)


	@unittest.skipIf(noCSE, 'No CSEBase')
	def test_spRelativeUnstructured(self):
		url = '%s~%s/%s' % (URL, CSEID, TestAddressing.cntRI)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)


	@unittest.skipIf(noCSE, 'No CSEBase')
	def test_absoluteStructured(self):
		url = '%s_/%s%s/%s/%s/%s' % (URL, SPID, CSEID, CSERN, aeRN, cntRN)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)
		url = '%s_/%s%s/-/%s/%s' % (URL, SPID, CSEID, aeRN, cntRN)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)


	@unittest.skipIf(noCSE, 'No CSEBase')
	def test_absoluteUnstructured(self):
		url = '%s_/%s%s/%s' % (URL, SPID, CSEID, TestAddressing.cntRI)
		r, rsc = RETRIEVE(url, TestAddressing.originator)
		self.assertEqual(rsc, RC.OK)
		self.assertEqual(findXPath(r, 'm2m:cnt/rn'), cntRN)

def run():
	suite = unittest.TestSuite()
	suite.addTest(TestAddressing('test_cseRelativeStructured'))
	suite.addTest(TestAddressing('test_cseRelativeUnstructured'))
	suite.addTest(TestAddressing('test_spRelativeStructured'))
	suite.addTest(TestAddressing('test_spRelativeUnstructured'))
	suite.addTest(TestAddressing('test_absoluteStructured'))
	suite.addTest(TestAddressing('test_absoluteUnstructured'))
	result = unittest.TextTestRunner(verbosity=testVerbosity, failfast=True).run(suite)
	return result.testsRun, len(result.errors + result.failures), len(result.skipped)

if __name__ == '__main__':
	_, errors, _ = run()
	sys.exit(errors)

