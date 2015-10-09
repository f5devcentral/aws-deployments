import time
from redis import Redis
from redis import ResponseError
from redis.exceptions import ConnectionError
import rq

REQUEST_PREFIX = 'f5demo.req-'
JOB_TIMEOUT = 600 #seconds

class JobManager(object):
	"""
		We use the python rq module to perform a non-blocking submit
		of provisioning requests from the service catalog app. 

		To provide status updates to the app, details are logged to 
		a seperate datastructure in Redis as provisioning continues.

		This module provides interfaces for redis use cases above.
		Connections to redis should not be made anywhere else. 
	"""
	def __init__(self):
		self.has_redis = True
		try:
			self.redis = Redis()

			# simple test that we can connect
			self.redis.keys()

			# connection okay, setup rq
			self.job_queue = rq.Queue(connection=self.redis)
		except ConnectionError:
			# redis isn't running 
			self.has_redis = False
			print 'WARNING: Redis connection failed.  Status not available for service catalog. '

	@staticmethod
	def get_hash(env_name):
		return REQUEST_PREFIX+env_name
		
	def submit_request(self, fn):
		""" Submit a job using the rq module"""
		self.job_queue.enqueue_call(func=fn, timeout=JOB_TIMEOUT)

	def configure_request(self, env_name, cmd):
		"""
			Flush old status updates for this env
			and create a new hash in redis
		"""
		if self.has_redis:
			self.redis.delete(JobManager.get_hash(env_name))
			self.redis.hmset(JobManager.get_hash(env_name), {"cmd": cmd})

	def update_request(self, env_name, msg='', err=''):
		"""
			Update the most recent msg for this environment
		"""
		if self.has_redis:
			status = {
				"last_update": time.strftime('%Y-%m-%d %H:%M:%S'),
				"err": err,
				"msg": msg
			}
			
			# make sure the hash for this env exists
			self.redis.hmset(JobManager.get_hash(env_name), status)

	def get_all_requests(self):
		requests = {}
		if self.has_redis:
			for k in self.redis.keys():
				if REQUEST_PREFIX in k:
					requests[k] = self.redis.hgetall(k)

		return requests

	def get_request_status(self, env_name):
		"""
		Try to look for updates for this env.
		  If one does not exist, return a dummy status.
		"""
		request = {"cmd": "Unknown", "msg": "No requests found"}
		if self.has_redis and self.redis.exists(JobManager.get_hash(env_name)):
			request = self.redis.hgetall(JobManager.get_hash(env_name))

		return request
