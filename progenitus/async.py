# Written by TheGurke 2011
"""Library for asynchronous methods with support for exceptions and operation
cancelation and arbitrary backends"""

import threading
import inspect


# Because python defines no type names for functions and generators
def _function():
	yield None
_generator = _function()
class _class(object):
	def method():
		pass
_instance_method = _class.method


def dummy_queuer(*args, **kwargs):
	"""Dummy queuer to remind the user to set the method_queuer"""
	raise Exception("Must set async.method_queuer!") # see below


# This is the queuer function that will take a function and call it at some
# later (idle) time. It must also work from within a thread, e.g. be thread
# safe.
method_queuer = dummy_queuer # e.g. glib.idle_add


# This class is needed so TaskHandler._run can check for the return type
class _ThreadInit(object):
	"""Wrapper class for a threaded function call"""
	def __init__(self, func):
		assert(isinstance(func, type(_function)))
		self.func = func


def threaded(func, *args, **kwargs):
	"""Return a threaded function call for a yield statement"""
	# This is just a wrapper
	if isinstance(func, type(_function)) or \
		isinstance(func, type(_instance_method)):
		return _ThreadInit(lambda: func(*args, **kwargs))
	if isinstance(func, type(_generator)):
		return _ThreadInit(lambda: run(func, *args, **kwargs))
	assert(False) # argument must be a function or generator


class TaskHandle(object):
	"""This is the handle for an asynchronous task. It can be used for
	cancellation"""
	
	def __init__(self, gen, except_handler):
		assert(isinstance(gen, type(_generator)))
		assert(isinstance(except_handler, type(_function)) or
			isinstance(except_handler, type(_instance_method)))
		self.generator = gen
		self.except_handler = except_handler
		self.thread = None
	
	def cancel(self):
		"""Cancel the corresponding task"""
		# Can also be called if the task has already been cancelled
		self.generator = None # prevent further yield starts
		# Should not close generator
		if self.thread is not None:
			pass
			# FIXME: Thread should be killed, but python does not support that
	
	def finished(self):
		"""Is this task finished?"""
		return self.generator is None
	
	def _run(self, result=None, _throwing=False):
		if self.generator is None:
			return # task has been cancelled in the mean time
		try:
			# Run the next step
			if _throwing:
				assert(isinstance(result, Exception))
				next_result = self.generator.throw(type(result), result)
			else:
				next_result = self.generator.send(result)
		except StopIteration:
			self.thread = None
			self.generator = None
			return
		except Exception as exc:
			self.generator.close() # run finally statements
			print inspect.trace() # debug code
			method_queuer(lambda: self.except_handler(exc))
				# Queue this because the handler should not be called out
				# of a thread
		else:
			if isinstance(next_result, _ThreadInit):
				thread_func = next_result.func
				# Run the returned function in a thread
				def task():
					try:
						result3 = thread_func()
					except Exception as exc:
						# hand the exception back to the main method
						method_queuer(lambda: self._run(exc, _throwing=True))
					else:
						method_queuer(lambda: self._run(result3))
				self.thread = threading.Thread(target=task)
				self.thread.daemon = True
				self.thread.start()
			else:
				# Queue the next part
				method_queuer(lambda: self._run(next_result))
				self.thread = None


def no_except_handler(exc):
	"""Don't handle exceptions, just pass them on"""
	raise exc


def start(generator, except_handler=no_except_handler):
	"""Start an async method asynchronously, returns thread handle"""
	assert(isinstance(generator, type(_generator))) # must be a generator!
	assert(isinstance(except_handler, type(_function)) or
		isinstance(except_handler, type(_instance_method)))
	
	# This is just a wrapper
	th = TaskHandle(generator, except_handler)
	method_queuer(th._run)
	return th


def run(generator):
	"""Run an async method synchronously"""
	assert(isinstance(generator, type(_generator))) # must be a generator!
	
	result = None
	try:
		while True:
			result = generator.send(result)
	except StopIteration:
		pass
	finally:
		generator.close()
	return result # FIXME: ?


def run_threaded(generator, except_handler=no_except_handler):
	"""Run an async method inside a thread, returns thread handle"""
	assert(isinstance(generator, type(_generator))) # must be a generator!
	assert(isinstance(except_handler, type(_function)) or
		isinstance(except_handler, type(_instance_method)))
	
	def task():
		yield threaded(run, generator)
	return start(task(), except_handler)



