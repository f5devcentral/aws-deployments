"""
Examples of setting up BIG-IP AWS via iControlREST 
"""

import json
import requests
import logging

logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

TARGET_IP="52.17.211.89"
USERNAME="admin"
PASSWORD="galileo"

INTERNAL_SELF="172.16.12.165/24"
EXTERNAL_SELF="172.16.13.165/24"

DEBUG=True

def debug(msg):
	if DEBUG is True:
		print msg

class iControlRest(object):
	def __init__(self, targetIp, username, password):

		self.host = "https://%s" % targetIp
		self.auth = (username, password)

		self.requests = requests

	def post(self, resource, data, unique_key):
		"""
			because REST is not really REST with BIG-IP, we need to 
			check to see if the object exists before posting....
		"""
		config_objects = self.get(resource)
		debug("resource  = {}".format(resource))
		debug("data = {}".format(data))
		debug("config objects = {}".format(config_objects))

		try:
		 	for i in config_objects["items"]:
				if i[unique_key] == data[unique_key]:
					print "Found a pre-existing config object with %s=%s, making HTTP PATCH request instead" % (unique_key, data[unique_key])
					url="{}/{}".format(resource, data[unique_key])
					
					# Working around this error from tmsh:
					# => {"code":400,"message":"\"network\" may not be specified in the context of the \"modify\" command.
					#   \"network\" may be specified using the following commands: create, list, show","errorStack":[]}
					if data.get("network", None) is not None:
						del data["network"]

					return self.patch(url, data)
		except KeyError:
			pass

		#there are no configuration items, key error in if statement above
		r = self.requests.post(url="{}/{}".format(self.host, resource), data=json.dumps(data),
			auth=self.auth, verify=False)
		return self.verify_response(r)
	
	def patch(self, resource, data):
		"""
			patch is easier, since we don't need to check on anything
		"""
		resource = "{}/{}".format(self.host, resource)
		r = self.requests.put(resource, data=json.dumps(data),
			auth=self.auth, verify=False)

		return self.verify_response(r)

	def get(self, resource):
		"""
			use to check whether objects already exist before we post
		"""

		r = self.requests.get("{}/{}".format(self.host, resource), auth=self.auth, verify=False)

		return self.verify_response(r)


	@staticmethod
	def verify_response(request):
		if request.status_code != requests.codes.ok:
			request.raise_for_status()

		return json.loads(request.text)


icr = iControlRest(TARGET_IP, USERNAME, PASSWORD)

# # get the device hostname
print "hostname = %s" % icr.get("mgmt/tm/sys/global-settings")["hostname"]

# # set aws access and secret keys
payload = {"awsAccessKey":"5678", "awsSecretKey":"5678"}
print "response text = %s" % icr.patch("mgmt/tm/sys/global-settings", payload)

# #create vlans
payload = {"name":"private", "interfaces":"1.2"}
print "response text = %s " % icr.post('mgmt/tm/net/vlan', payload, "name")
payload = {"name":"public", "interfaces":"1.1"}
print "response text = %s " % icr.post('mgmt/tm/net/vlan', payload, "name")

#create self-ips
payload = {"name":"public", "address":EXTERNAL_SELF, "vlan":"public"}
print "response text = %s " % icr.post('mgmt/tm/net/self', payload, "name")
payload = {"name":"private", "address":INTERNAL_SELF, "vlan":"private"}
print "response text = %s " % icr.post('mgmt/tm/net/self', payload, "name")

# set the default gateway pool
payload = { "name": "default_gateway_pool", "members":[ {"name":"172.16.2.1:0","address":"172.16.2.1"}, {"name":"172.16.12.1:0","address":"172.16.12.1"} ], "monitor": "gateway_icmp" }
print "response text = %s " % icr.post('/mgmt/tm/ltm/pool', payload, "name")

# set the default gateway pool
payload = { "name": "pool_member_gateway_pool", "members":[ {"name":"172.16.3.1:0","address":"172.16.3.1"}, {"name":"172.16.13.1:0","address":"172.16.13.1"} ], "monitor": "gateway_icmp" }
print "response text = %s " % icr.post('/mgmt/tm/ltm/pool', payload, "name")

# set the default route (using the default gateway pool)
payload = {"name": "default_route", "network": "default", "pool": "/Common/default_gateway_pool" }
print "response text = %s " % icr.post('/mgmt/tm/net/route', payload, "name")

# set the default route (using the default gateway pool)
payload = { "name": "AZ1_pool_member_network", "network": "172.16.4.0/24", "pool": "/Common/pool_member_gateway_pool" }
print "response text = %s " % icr.post('/mgmt/tm/net/route', payload, "name")
payload = { "name": "AZ2_pool_member_network", "network": "172.16.14.0/24", "pool": "/Common/pool_member_gateway_pool" }
print "response text = %s " % icr.post('/mgmt/tm/net/route', payload, "name")



