"""
test_lifecycle_single_standalone.py

In general, our approach to using ansible is to first progamatically
create the ansible inventory files for a deployment.  We do this using
the 'inventory_manager' role.  In some sense, the inventory provides a
"definition" of what is to be deployed. Various provisioning workflows
are executed given this environment inventory.

This test module executes a subset of provisioning workflows can code branches
for *one* of these definitions, specifically the single-standalone
deployment mode:

This should exercise the following codepaths:
-deployment_model=lb_only
-deploy_analytics=false

"""

import sys 
import json
import pytest
from time import time
from f5_aws.config import Config
from f5_aws.environment_manager import EnvironmentManager, EnvironmentManagerFactory

config = Config().config
region_for_lifecyle_tests = config['regions'][0]
deployment_models = config['deployment_models']

# class TestLifecycleSingleStandalone(object):
#     @classmethod
#     # def setup_class(cls):
#     #     """ setup any state specific to the execution of the given class (which
#     #     usually contains tests).
#     #     """
#     #     timestamp = int(time())
#     #     # first, we need to initialize the environment we are going to deploy
#     #     # initialize the inventory
#     #     cls.init_inputs = {
#     #         "env_name": "ut-standalone-{}".format(timestamp),
#     #         "extra_vars": {
#     #             "deployment_model": "single-standalone",
#     #             "deployment_type": "lb_only",
#     #             "region": region_for_lifecyle_tests,
#     #             "zone": region_for_lifecyle_tests + "b"
#     #         },
#     #         "cmd": "init"
#     #     }
#     #     cls.deploy_inputs = {
#     #         "env_name": "ut-standalone-{}".format(timestamp),
#     #         "cmd":"deploy"
#     #     }
#     #     cls.teardown_inputs = {
#     #         "env_name": "ut-standalone-{}".format(timestamp),
#     #         "cmd":"teardown"
#     #     }
#     #     cls.remove_inputs = {
#     #         "env_name": "ut-standalone-{}".format(timestamp),
#     #         "cmd":"remove"
#     #     }
#     def setup_class(cls):
#         """ setup any state specific to the execution of the given class (which
#         usually contains tests).
#         """
#         timestamp = int(time())
#         # first, we need to initialize the environment we are going to deploy
#         # initialize the inventory
#         cls.init_inputs = {
#             "env_name": "ut-standalone-1447974075",
#             "extra_vars": {
#                 "deployment_model": "single-standalone",
#                 "deployment_type": "lb_only",
#                 "region": region_for_lifecyle_tests,
#                 "zone": region_for_lifecyle_tests + "b"
#             },
#             "cmd": "init"
#         }
#         cls.deploy_inputs = {
#             "env_name": "ut-standalone-1447974075",
#             "cmd":"deploy"
#         }
#         cls.teardown_inputs = {
#             "env_name": "ut-standalone-1447974075",
#             "cmd":"teardown"
#         }
#         cls.remove_inputs = {
#             "env_name": "ut-standalone-1447974075",
#             "cmd":"remove"
#         }

#     @classmethod
#     def teardown_class(cls):
#         """ teardown any state that was previously setup with a call to
#         setup_class.
#         """
#         em = EnvironmentManagerFactory(**self.teardown_inputs)
#         outputs = getattr(em, "teardown")()
#         em.remove()

#     def test_init_environment(self):
#         """ initialize the ansible inventory"""
#         em = EnvironmentManagerFactory(**self.init_inputs)
#         outputs = getattr(em, "init")()
#         assert (len(outputs["playbook_results"].playbooks) > 0 and
#                 outputs["playbook_results"].statuscode == 0)

#     def test_deploy_environment(self):
#         """
#         Use ansible to deploy the environment - this is long
#         running, as long as 25 minutes
#         """
#         em = EnvironmentManagerFactory(**self.deploy_inputs)
#         outputs = getattr(em, "deploy")()
#         assert (len(outputs["playbook_results"].playbooks) > 0 and
#                 outputs["playbook_results"].statuscode == 0)

#         # once the environment is deployed, we can check for a number
#         #  items we are expecting in the CLI output
#         login_info = em.login_info()

#         app = ''
#         virtual_server = ''

#         assert len(login_info['bigip']) == 1
#         for host, variables in login_info['bigip'].iteritems():
#             virtual_server_ip = variables["elastic_ips"][0]
#             assert len(variables["elastic_ips"]) > 0
#             assert len(variables["virtual_servers"]) > 0
#             assert variables["https"]
#             assert variables["ssh"]

#         assert len(login_info['apphost']) == 1
#         for host, variables in login_info['apphost'].iteritems():
#             app_ip = variables['http'][0]
#             assert variables["http"]
#             assert variables["ssh"]

#         assert len(login_info['gtm']) == 1
#         for host, variables in login_info['gtm'].iteritems():
#             assert len(variables["elastic_ips"]) > 0
#             assert len(variables["wideips"]) > 0
#             assert variables["https"]
#             assert variables["ssh"]

#         # finally, we can do a simple curl against the http address of the app
#         #  and the https address of the virtual server
#         r = requests.get('https://{}'.format(virtual_server))
#         assert re.match('20[0-9]', string(r.status_code))

#         r = requests.get('{}'.format(app))
#         assert re.match('20[0-9]', string(r.status_code))
    
