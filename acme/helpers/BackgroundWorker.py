#
#	BackgroundWorker.py
#
#	(c) 2020 by Andreas Kraft
#	License: BSD 3-Clause License. See the LICENSE file for further details.
#
#	This class implements a background process.
#

from __future__ import annotations
from Logging import Logging
import time, random, sys
from threading import Thread
from typing import Callable, List, Dict, Any


class BackgroundWorker(object):

	def __init__(self, updateIntervall:float, callback:Callable, name:str=None, startWithDelay:bool=False, count:int=None, dispose:bool=True, id:int=None) -> None:
		self.updateIntervall = updateIntervall
		self.callback = callback
		self.running = False
		self.workerThread: Thread = None
		self.name = name
		self.startWithDelay = startWithDelay
		self.count = count
		self.numberOfRuns = 0
		self.dispose = dispose	# Only run once, then remove itself from the pool
		self.id = id


	def start(self, **args:Any) -> BackgroundWorker:
		if self.running:
			self.stop()
		Logging.logDebug('Starting worker thread: %s' % self.name)
		self.running = True
		self.args = args
		self.workerThread = Thread(target=self.work)
		self.workerThread.setDaemon(True)	# Make the thread a daemon of the main thread
		self.workerThread.name = self.name
		self.workerThread.start()
		return self


	def stop(self) -> BackgroundWorker:
		Logging.logDebug('Stopping worker thread: %s' % self.name)
		# Stop the thread
		self.running = False
		if self.workerThread is not None and self.updateIntervall is not None:
			self.workerThread.join(self.updateIntervall + 5) # wait a short time for the thread to terminate
			self.workerThread = None
		# Note: worker is removed in _postCall()
		return self



	def work(self) -> None:
		self.numberOfRuns = 0
		if self.startWithDelay:	# First execution of the worker after a sleep
			self._sleep()
		while self.running:
			result = True
			try:
				self.numberOfRuns += 1
				result = self.callback(**self.args)
			except Exception as e:
				Logging.logErr(str(e))
			finally:
				if self.count is not None and self.numberOfRuns >= self.count:
					self.running = False

				if result and self.running:
					self._sleep()
					continue

			# if we reached this we will stop
			Logging.logDebug('Stopping worker thread: %s' % self.name)
			self.running = False
		self._postCall()


	# self-made sleep. Helps in speed-up shutdown etc
	divider = 5.0
	def _sleep(self) -> None:
		if self.updateIntervall < 1.0:
			time.sleep(self.updateIntervall)
		else:
			for i in range(0, int(self.updateIntervall * self.divider)):
				time.sleep(1.0 / self.divider)
				if not self.running:
					break


	def _postCall(self) -> None:
		"""	Called after execution finished.
		"""
		if self.dispose:
			BackgroundWorkerPool._removeBackgroundWorkerFromPool(self)


	def __repr__(self) -> str:
		return 'BackgroundWorker(name=%s, callback=%s, running=%r, updateIntervall=%f, startWithDelay=%r, numberOfRuns=%s, dispose=%r, id=%s)' % (self.name, str(self.callback), self.running, self.updateIntervall, self.startWithDelay, self.numberOfRuns, self.dispose, self.id)



class BackgroundWorkerPool(object):

	backgroundWorkers:Dict[int, BackgroundWorker] = {}

	def __new__(cls, *args:str, **kwargs:str) -> BackgroundWorkerPool:
		raise TypeError('%s may not be instantiated' % BackgroundWorkerPool.__name__)


	@classmethod
	def newWorker(cls, updateIntervall:float, workerCallback:Callable, name:str=None, startWithDelay:bool=False, count:int=None, dispose:bool=True) -> BackgroundWorker:
		"""	Create a new background worker that periodically executes the callback.
		"""
		# Get a unique ID
		while True:
			if (id := random.randint(1,sys.maxsize)) not in cls.backgroundWorkers:
				break
		worker = BackgroundWorker(updateIntervall, workerCallback, name, startWithDelay, count=count, dispose=dispose, id=id)
		cls.backgroundWorkers[id] = worker
		return worker


	@classmethod
	def newActor(cls, delay:float, workerCallback:Callable, name:str=None, dispose:bool=True) -> BackgroundWorker:
		"""	Create a new background worker that runs only once after a delay (the 'delay' may be 0.0s, though).
		"""
		return cls.newWorker(delay, workerCallback, name=name, startWithDelay=delay>0.0, count=1, dispose=dispose)


	@classmethod
	def findWorkers(cls, name:str=None, running:bool=None) -> List[BackgroundWorker]:
		return [ w for w in cls.backgroundWorkers.values() if (name is None or w.name == name) and (running is None or running == w.running) ]


	@classmethod
	def stopWorkers(cls, name:str) -> List[BackgroundWorker]:
		workers = cls.findWorkers(name=name)
		for w in workers:
			w.stop()
		return workers


	@classmethod
	def removeWorkers(cls, name:str) -> List[BackgroundWorker]:
		workers = cls.stopWorkers(name)
		# Most workers should be removed when stopped, but remove the rest here
		for w in workers:
			cls._removeBackgroundWorkerFromPool(w)
		return workers


	@classmethod
	def _removeBackgroundWorkerFromPool(cls, worker:BackgroundWorker) -> None:
		if worker is not None and worker.id in cls.backgroundWorkers:
			del cls.backgroundWorkers[worker.id]


