#!/usr/bin/python

"""
ansible module for managing configuration resource on BIG-IP over iControlREST.
"""

# bigip_config

import json
import requests

from requests.exceptions import ConnectionError, HTTPError, Timeout, TooManyRedirects

class BigipConig(object):
  def __init__(self, module):
    self.host = module.params["host"]
    self.user = module.params["user"]
    self.password = module.params["password"]
    self.collection_path = module.params["collection_path"]
    self.resource_id = module.params["resource_id"]
    self.resource_key = modules.params["resource_key"]

    self.hosturl = "https://%s" % self.host
    self.auth = (self.user, self.password)

    self.requests = requests

  def get_full_resource_id(self):
    if self.resource_id is not None:
        return self.resource_id
    else:
        # need to extract the id from payload
        return self.payload[self.resource_key]

  def _get_full_resource_path():
    return '%s/%s' % (self.collection_path, self.resource_id())

  def resource_exists(self):
    exists = False
    response_text = self.http("get", self.collection_path)

    items = response_text.get("items", None)
    if items is not None:
      for i in items:
        if i[self.unique_key] == self.payload[self.unique_key]:
          exists = True
          break
    return exists

  def _get_safe_patch_payload(self):
    safe_payload = self.payload.copy(deep=True)
    
    # Working around this error from tmsh:
    # => {"code":400,"message":"\"network\" may not be specified in the context of the \"modify\" command.
    #   \"network\" may be specified using the following commands: create, list, show","errorStack":[]}
    if self.payload.get("network", None) is not None:
      del self.payload["network"]

    return safe_payload

  def create_resource(self):
    return self.http("post", self.collection_path, self.payload)
    

  def update_resource(self):
    return self.http("patch", self._get_full_resource_path(),
      self._get_safe_patch_payload())

  def delete_resource(self):
    return self.http("delete", self._get_full_resource_path())
     #response_text

  def http(self, method, host, payload=''):
    print 'HTTP %s %s: %s' % (method, host, payload)
    method = getattr(requests, method.lower(), None)
    if method is None:
      raise NotImplemented
    try:
      if payload != '':
        request = method(url=host, data=json.dumps(payload), auth=self.auth, verify=False)
      else:
        request = method(url=host, auth=self.auth, verify=False)

      if request.status_code != status.codes.ok:
        request.raise_for_status()

      rc = 0
      out = json.loads(request.text)
      err = ''
    except (ConnectionError, HTTPError, Timeout, TooManyRedirects) as e
      rc = 1
      out = json.loads(request.text)
      err = e.message

    print 'HTTP %s returned: %s' % (method, request.text)

    return (rc, out, err)

def main():
  module = AnsibleModule(
    argument_spec = dict(
      state=dict(required=True, default='present', choices=['present', 'absent'], type='str'),
      user=dict(required=True, default=None, type='str'),
      password=dict(required=True, default=None, type='str'),
      resource=dict(required=False, default=None, type='str'),
      # specific to state=present
      payload=dict(required=False, default=None, type='str'),
      unique_key=dict(required=False, default=None, type='str'),
    ),
    mutually_exclusive = [['resource_id'],['resource_key']]
    supports_check_mode=True
  )

  bigip_config = BigipConfig(module)

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
      (rc, out, err) = user.delete_resource()
      if rc != 0:
        module.fail_json(name=bigip_config.collection_path, msg=err, rc=rc)
  elif bigip_config.state == 'present':
    if not bigip_config.resource_exists():
      if module.check_mode:
        module.exit_json(changed=True)
      (rc, out, err) = bigip_config.create_resource()
      result['resource'] = bigip_config._get_full_resource_path()
    else:
      # modify user (note: this function is check mode aware)
      (rc, out, err) = bigip_config.update_resource()
    
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


