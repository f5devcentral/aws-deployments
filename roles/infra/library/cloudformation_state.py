#!/usr/bin/python

"""
ansible module for managing configuration resources on BIG-IP over iControlREST.
"""

import sys
import json
import requests
from copy import deepcopy

from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects

class CloudFormationState(object):
  def __init__(self, module):
    self.stack_name = module.params["host"]
    self.state = module.params["state"]

  def resource_exists(self):
    #for collections that we want to patch (for example sys/global-settings)
    # there is no resource_key which we can use to determine existance
    if self.resource_key is None:
      return False

    exists = False
    (rc, out, err) = self.http("get", self.collection_path)

    if rc != 0:
      raise ValueError("Bad return code from HTTP GET. %s " % err)

    items = out.get("items", None)
    if items is not None:
      for i in items:
        if i[self.resource_key] == self.payload[self.resource_key]:
          exists = True
          break
    return exists


def main():

  print 'main()'
  module = AnsibleModule(
    argument_spec = dict(
      state=dict(default='present', choices=['present', 'absent'], type='str'),
      user=dict(required=True, default=None, type='str'),
      host=dict(required=True, default=None, type='str'),
      password=dict(required=True, default=None, type='str'),
      collection_path=dict(required=False, default=None, type='str'),
      # specific to state=present
      payload=dict(required=False, default=None, type='str'),
      resource_id=dict(required=False, default=None, type='str'),
      resource_key=dict(required=False, default=None, type='str'),
    ),
    mutually_exclusive = [['resource_id','resource_key']],
    supports_check_mode=True
  )

  cfstate = CloudFormationState(module)

  rc = None
  out = ''
  err = ''
  result = {}
  result['collection_path'] = bigip_config.collection_path
  result['state'] = bigip_config.state
  
  if bigip_config.state == 'absent':
    if bigip_config.resource_exists():
      if module.check_mode:
        module.exit_json(changed=True)
      (rc, out, err) = bigip_config.delete_resource()
      if rc != 0:
        module.fail_json(name=bigip_config.collection_path, msg=err, rc=rc)
  elif bigip_config.state == 'present':
    (rc, out, err) = bigip_config.create_or_update_resource()
    
    if rc != 0:
      module.fail_json(name=bigip_config.collection_path, msg=err, rc=rc)

  if rc is None:
    result['changed'] = False
  else:
    result['changed'] = True
  if out:
    result['out'] = out
  if err:
    result['err'] = err

  module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
main()


