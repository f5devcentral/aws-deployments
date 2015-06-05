
from bigip_config import BigipConfig


class Module(object):
    def __init__(self, **kwargs):
    	self.params = {}
    	for k, v in kwargs.iteritems():
    		self.params[k] = v

tests = [
	Module(
		host="52.17.211.89",
		user="restadmin",
		password="galile0",
		state="present",
		payload='{"name":"fastL4-route-friendly", "resetOnTimeout":"disabled", "looseInitialization": "disabled", "looseClose": "disabled" }',
		collection_path="mgmt/tm/ltm/profile/fastl4",
		resource_id=None,
		resource_key="name"
	),
	Module(
		host="52.17.211.89",
		user="restadmin",
		password="galile0",
		state="present",
		payload='{ "awsAccessKey":"12345", "awsSecretKey":"678910"}',
		collection_path="mgmt/tm/sys/global-settings",
		resource_id=None,
		resource_key=None
	),
	Module(
		host="52.17.211.89",
		user="restadmin",
		password="galile0",
		state="present",
		payload='{ "name": "default_gateway_pool", "members":[ {"name":"172.16.2.1:0","address":"172.16.2.1"}, {"name":"172.16.12.1:0","address":"172.16.12.1"} ], "monitor": "gateway_icmp" }',
		collection_path="mgmt/tm/ltm/pool",
		resource_id=None,
		resource_key="name"
	),
	# Module(
	# 	host="52.17.211.89",
	# 	user="restadmin",
	# 	password="galile0",
	# 	state="present",
	# 	payload='{"name":"private", "interfaces":"1.1"}',
	# 	collection_path="mgmt/tm/net/vlan",
	# 	resource_id=None,
	# 	resource_key="name"
	# )
	Module(
		host="52.17.211.89",
		user="restadmin",
		password="galile0",
		state="present",
		payload='{"name":"public", "address":"172.16.12.128/24", "vlan":"public"}',
		collection_path="mgmt/tm/net/self",
		resource_id=None,
		resource_key="name"
	),

]

for m in tests:
	bc = BigipConfig(m)

	print 'bigip_config.create_or_update_resource() = {}'.format(bc.create_or_update_resource())



