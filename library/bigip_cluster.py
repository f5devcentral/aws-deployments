#!/usr/bin/env python 

DOCUMENTATION = '''
---
module: bigip_cluster
short_description: "Manages F5 BIG-IP Device Services Clusters"
description:
    - "Manages F5 BIG-IP Device Services Clusters"
version_added: "X.X"
author: Alex Applebaum
notes:
    - "Requires BIG-IP software version >= 11"
    - "Best run as a local_action in your playbook"
    - "Assumes all clustering work done in "/Common"
requirements:
    - bigsuds 
options:
    username:
        description:
            - BIG-IP username
        required: true
        default: null
        choices: []
        aliases: []
    password:
        description:
            - BIG-IP password
        required: true
        default: null
        choices: []
        aliases: []
    state:
        description:
            - cluster state
        required: false
        default: present
        choices: ['present', 'absent']
        aliases: []
    action:
        description:
            - configure cluster
        required: true
        default: cluster
        choices: ['cluster']
        aliases: []
    ha_type:
        description:
            - The type of cluster (standalone, pair or scalen)
              * Not implemented yet. Will probably dictate algorithm of traffic groups to create/deploy. 
        required: false
        default: []
        choices: ['standalone','pair','scalen']
        aliases: []
    bigip_cluster_name:
        description:
            - name for device failover group
        required: false
        default: my_sync_failover_group
        choices: []
        aliases: []
    device_names:
        description:
            - List of DSC device object names. Should generally match dns hostname.
        required: true
        default: null
        choices: []
        aliases: []
    api_addrs:
        description:
            - List of each BIG-IP's iControl address that is reachable from this program.
        required: true
        default: null
        choices: []
        aliases: []
    mgmt_addrs:
        description:
            - List of each BIG-IP's mgmt address
        required: true
        default: null
        choices: []
        aliases: []
    ha_addrs:
    description:
        - List of each BIG-IP's failover address (list length should match device_names)
    required: true
    default: none
    choices: []
    aliases:
    mirror_addrs:
    description:
        - List of each BIG-IPs primary mirror address (list length should match device_names)
    required: false
    default: none
    choices: []
    aliases:

'''

EXAMPLES = '''

## playbook task examples:

---
# file bigip_cluster.yml
# ...
- hosts: localhost
  tasks:
  - name: Simple create cluster
    bigip_cluster:
	username: admin
	password: mysecret
	state: present
	action: cluster
	ha_type: pair
	bigip_cluster_name: my_sync_failover_group
	api_addrs: [ 55.55.55.55, 55.55.55.56 ]
	device_names: [ lb1.mydomain.com, lb2.mydomain.com ]
	mgmt_addrs: [ 10.0.0.201, 10.0.0.202 ]
	ha_addrs: [ 10.0.1.201, 10.0.1.202 ]
	mirror_addrs: [ 10.0.1.201, 10.0.1.202 ]

  # NOT IMPLEMENTED YET
  - name: Simple delete cluster
    bigip_cluster:
	username: admin
	password: mysecret
	state: absent
	action: cluster
        api_addrs: [ 55.55.55.55, 55.55.55.56 ]
        device_names: [ lb1.mydomain.com, lb2.mydomain.com ]

'''

import os
import sys
import json
import bigsuds
# Workaround to disable certificate verification in urllib. 
# Necessary evil for initial provisioning.
import ssl
ssl._create_default_https_context = ssl._create_unverified_context


def main():

    result = {}
    changed = False

    argument_spec = dict(
            username=dict(type='str', aliases=['username', 'admin'], required=True),
            password=dict(type='str', aliases=['password', 'pwd'], required=True, no_log=True),
            state=dict(type='str', choices=['present', 'absent'], required=True),
            action=dict(type='str', choices=['cluster'],  required=True),
            ha_type=dict(type='str', choices=['standalone','pair','scalen'], required=False),
            bigip_cluster_name=dict(type='str', default="my-sync-failover-group"),
            device_names=dict(type='list'),
            api_addrs=dict(type='list'),
            mgmt_addrs=dict(type='list'),
            ha_addrs=dict(type='list'),
            mirror_addrs=dict(type='list'),
            timeout=dict(type='str',required=False, default=None),
	    address_isolation=dict(default=False),
	    strict_route_isolation=dict(default=False)
    )

    module = AnsibleModule(
        argument_spec = argument_spec,
    )

    username = module.params['username']
    password = module.params['password']
    timeout = module.params['timeout']
    address_isolation = module.params['address_isolation']
    strict_route_isolation = module.params['strict_route_isolation']

    state = module.params['state']
    action = module.params['action']
    ha_type = module.params['ha_type']
    bigip_cluster_name = module.params['bigip_cluster_name']
    device_names = module.params['device_names']
    bigip_api_addr_list = module.params['api_addrs']
    bigip_mgmt_addr_list = module.params['mgmt_addrs']
    bigip_ha_addr_list = module.params['ha_addrs']
    bigip_mirror_addr_list = module.params['mirror_addrs']
    #bigip_image not used
    bigip_image = ''

    num_bigips = len(device_names)

    #Quick validation
    if device_names is None or \
           bigip_mgmt_addr_list is None or \
           bigip_ha_addr_list is None:
           module.fail_json(msg='device object names are required when creating a cluster. device object names are usually the hostname')

    if action == 'cluster':

	for BIGIP_INDEX in range(0, num_bigips):

	    try:
		# Initalize the bigsuds connection object to SEED node
		bigip_obj = bigsuds.BIGIP(
			    hostname = bigip_api_addr_list[BIGIP_INDEX],
			    username = username,
			    password = password,
			    )
	    except Exception, e:
		module.fail_json(msg="bigip suds object creation failed. received exception: %s" % e)

	    try:

		existing_device_name = bigip_obj.Management.Device.get_local_device()
		# existing_hostname = bigip_obj.System.Inet.get_hostname()
		# print json.dumps({"existing_device_name": existing_device_name,
		#                 "device_name": device_name})

		# The default DSC device_name object is bigip1 on every device 
		# so have to reset device trust in order to reset the device_name to be unique. 
		# device_name could be arbitrary/simple like bigip1, bigip2.
		# If not already something unique like a hostname, 
		# In the end, best practice is to match hostname but well just use name provided 
		if existing_device_name != "/Common/bigip1" or ("/Common/" + device_names[BIGIP_INDEX]):
		    bigip_obj.Management.Trust.reset_all(
					    device_object_name = device_names[BIGIP_INDEX],
					    keep_current_authority = 'true',
					    authority_cert = '',
					    authority_key = '',
					  )

		    result = { "changed": True, "Reset Device Trust" : True }
		    time.sleep(15)

		############################################################
		# Begin Setting HA Channel Properities on each device object
		############################################################
	        
                # TODO: Add idempotence to these calls. Check if exists/matches first and report if changed

		# Set ConfigSync Address 
		bigip_obj.Management.Device.set_configsync_address( devices = [ device_names[BIGIP_INDEX] ], 
								    addresses = [ bigip_ha_addr_list[BIGIP_INDEX] ] )

		# Set Failover Address
		fo_ints = [ bigip_mgmt_addr_list[BIGIP_INDEX], bigip_ha_addr_list[BIGIP_INDEX] ]
		unicast_objs = []
		for i in range(len(fo_ints)):
		    unicast_obj = {
				    'source'    : { 'address' : fo_ints[i], 'port' : 1026 },
				    'effective' : { 'address' : fo_ints[i], 'port' : 1026 }
				  }
		    unicast_objs.append(unicast_obj)

		bigip_obj.Management.Device.set_unicast_addresses(
							    devices =   [ device_names[BIGIP_INDEX] ],
							    addresses = [ unicast_objs ]
							)
	      
		# Set Mirror Addresses
		bigip_obj.Management.Device.set_primary_mirror_address(
								devices = [ device_names[BIGIP_INDEX] ],
								addresses = [ bigip_ha_addr_list[BIGIP_INDEX] ]
							    )
    #             bigip_obj.Management.Device.set_secondary_mirror_address(
    #                                                             devices = [ device_names[BIGIP_INDEX] ],
    #                                                             addresses = [ bigip_ha_addr_list[BIGIP_INDEX] ]
    #                                                         )
    # 

                # For now, Just rolling up summary that all calls were made
		result = { "changed": True, "Device Object Configured" : True }

	    except Exception, e:
		module.fail_json(msg="device object configuration failed. received exception: %s" % e)

	### END DEVICE OBJECT LOOP ###

	# GO TO SEED DEVICE (default = 1st device in list) 
        # AND CREATE THE CLUSTER
        # FIRST MAKE SURE NOT JUST ONE DEVICE IN LIST (i.e. we have STANDALONE)
	if len(device_names) > 1: 

	    try:
		# Initalize a bigsuds connection object to SEED node
		seed_bigip_obj = 	bigsuds.BIGIP(
				    hostname = bigip_api_addr_list[0],
				    username = username,
				    password = password,
				    )
	    except Exception, e:
		module.fail_json(msg="seed bigip suds object creation failed. received exception: %s" % e)


	    try:
		peer_exists = False
		device_group_exists = False

		# Check to see if Device Trust Group exists / already contains a peer device
		existing_peers = seed_bigip_obj.Management.Device.get_list()
		for device in existing_peers:
		    if device == device_names[1]:
			 peer_exists = True
			 break

		if bigip_cluster_name == None:
		    bigip_cluster_name = "my-sync-failover-group"

		# Check to see if there's a sync failover group
		existing_device_groups = seed_bigip_obj.Management.DeviceGroup.get_list()
		for group in existing_device_groups:
		    if group == ("/Common/" + bigip_cluster_name):
			 device_group_exists = True
			 break


		if not peer_exists:
		    for i in range(len(device_names)-1):

			    # Start adding peers
			    seed_bigip_obj.Management.Trust.add_authority_device(
							    address = bigip_api_addr_list[i + 1],
							    username = username,
							    password = password,
							    device_object_name = device_names[i + 1],
							    browser_cert_serial_number = '',
							    browser_cert_signature = '',
							    browser_cert_sha1_fingerprint = '',
							    browser_cert_md5_fingerprint = '',
							  )

		if not device_group_exists:

		    # Create Sync-Failover Group. 
		    device_group_created = seed_bigip_obj.Management.DeviceGroup.create(  
								device_groups = [ bigip_cluster_name ],
								types = [ "DGT_FAILOVER" ]
								)

		    # Due to, Bug alias 479071 TG initial-placement influenced by sync-failover DG w/auto-sync enabled 
		    # either need to disaable auto-sync when first creating sync-failover-group
		    # or first offline peers before adding them 
		    seed_bigip_obj.Management.DeviceGroup.set_autosync_enabled_state (
								device_groups = [ bigip_cluster_name ],
								states = [ "STATE_DISABLED" ]
								)
		    
		    # Add device Sync-Failover Group. 
		    add_devices = seed_bigip_obj.Management.DeviceGroup.add_device(  
								  device_groups = [ bigip_cluster_name ],
								  devices = [ device_names ]
								  )

		    #Sleep for 15 seconds to make sure devices are added
		    time.sleep(15)
		    # Initiate a Sync Request
		    sync_request = seed_bigip_obj.System.ConfigSync.synchronize_to_group_v2(
						    group = bigip_cluster_name,
						    device = device_names[0],
						    force = True
						    )

		    # Can now re-enable auto-sync  
		    seed_bigip_obj.Management.DeviceGroup.set_autosync_enabled_state (
								device_groups = [ bigip_cluster_name ],
								states = [ "STATE_ENABLED" ]
								)

		# Need extra validation here before returning true/Cluster successfully created		
		result = { "changed": True, "Cluster Created" : True }

	    except Exception, e:
		module.fail_json(msg="Cluster creation failed. received exception: %s" % e)

#  POTENTIAL FOR FUTURE:
# 	if action == 'traffic_group':
# 	
# 	    # exists = bigip_obj.cluster.traffic_group_exists( traffic_group_name )
# 	    existing_traffic_groups = bigip_obj.Management.TrafficGroup.get_list()
#             for group in existing_traffic_groups:
#                     if group == traffic_group_name:
#                          traffic_group_exists = True
#                          break	
# 	    
# 	    if not traffic_group_exists:
# 		# bigip_obj.cluster.create_traffic_group ( traffic_group_name ) 
#                 bigip_obj.Management.TrafficGroup.create( traffic_groups = [traffic_group_name] )
# 

 
    # module.exit_json(changed=changed, content=result)
    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
