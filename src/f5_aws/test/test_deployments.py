import sys 
import json
import pytest

from f5_aws.config import Config
from f5_aws.runner import EnvironmentManager, EnvironmentManagerFactory

config = Config().config
region_for_lifecyle_tests = config['regions'][0]
deployment_models = config['deployment_models']
#deployment_models = ['single-standalone']

###
# It is possible to use this test module to run through deployments of each 
# type, from init to remove.  Not done at current time to due expense of 
# doing this....literally, it would probably cost $50 to run each time...
###

model_stages = {
  "single-standalone":
    [ {"stage": "init",
        "inputs":
         {
            "env_name": "ut-standalone",
            "extra_vars": {
              "deployment_model": "single-standalone",
              "deployment_type": "lb_only",
              "region": region_for_lifecyle_tests,
              "zone": region_for_lifecyle_tests+"b",
              "image_id": "mutzel/all-in-one-hackazon"}
          }
      },
      # {"stage": "deploy",
      #  "inputs":
      #   {
      #       "env_name": "ut-standalone"
      #   }
      # },
      # # {stage: "info"},
      # {"stage": "teardown"},
      {"stage": "remove",
       "inputs":
        {
            "env_name": "ut-standalone"
        }
      }
    ],
  "single-cluster":
    [ {"stage": "init",
        "inputs":
          {
            "env_name": "ut-cluster",
            "extra_vars": {
              "deployment_model": "single-cluster",
              "deployment_type": "lb_only",
              "region": region_for_lifecyle_tests,
              "zone": region_for_lifecyle_tests+"b",
              "image_id": "mutzel/all-in-one-hackazon"}
          }
      },
      # {"stage": "deploy"},
      # #{stage: "info"},
      # {"stage": "teardown"},
      {"stage": "remove",
       "inputs":
        {
            "env_name": "ut-cluster"
        }
      }
    ],
  "cluster-per-zone":
    [ {"stage": "init",
        "inputs":
          {
            "env_name": "ut-cluster-per-zone",
            "extra_vars": {
              "deployment_model": "cluster-per-zone",
              "deployment_type": "lb_only",
              "region": region_for_lifecyle_tests,
              "zones": [region_for_lifecyle_tests+"b", region_for_lifecyle_tests+"c"],
              "image_id": "mutzel/all-in-one-hackazon"}
          }
      },
      # {"stage": "deploy"},
      # #{stage: "info"},
      # {"stage": "teardown"},
      
      {"stage": "remove",
       "inputs":
        {
            "env_name": "ut-cluster-per-zone"
        }
      }
    ],
  "standalone-per-zone":
    [ {"stage": "init",
        "inputs":
          {
            "env_name": "ut-standalone-per-zone",
            "extra_vars": {
              "deployment_model": "standalone-per-zone",
              "deployment_type": "lb_only",
              "region": region_for_lifecyle_tests,
              "zones": [region_for_lifecyle_tests+'b', region_for_lifecyle_tests+"c"],
              "image_id": "mutzel/all-in-one-hackazon"}
          }
      },
      # {"stage": "deploy"},
      # #{stage: "info"},
      # {"stage": "teardown"},
      
      {"stage": "remove",
       "inputs":
        {
            "env_name": "ut-standalone-per-zone"
        }
      }
    ], 
}

# scope=module => this setup function will be run once before 
#  executing all the test methods in this module
@pytest.fixture(scope="function", params=deployment_models)
def model(request):
  return request.param

# run through all the steps for a deployment
def test_model_lifecycle(model):
  for s in model_stages[model]:
    inputs = s['inputs']
    inputs["cmd"] = s["stage"]

    # reinstantiate EM each time as we are doing in ./bin/f5aws
    #  all playbooks contexts should run successfully (exit code 0)
    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, inputs["cmd"])()
    
    # the stage has custom outputs, check these
    if "outputs" in s["stage"]:
      pass

    # otherwise assume that we just ran some playbooks
    #  check that playbooks executed properly
    assert (len(outputs["playbook_results"].playbooks) > 0 and
      outputs["playbook_results"].statuscode == 0)


def test_model_lifecycle_w_waf(model):
  for s in model_stages[model]:
    inputs = s["inputs"]
    inputs["cmd"] = s["stage"]

    # add the deployment_type=lb_and_waf
    if inputs["cmd"] == "init":
      inputs["extra_vars"]["deployment_type"] = "lb_and_waf"

    # reinstantiate EM each time as we are doing in ./bin/f5aws
    #  all playbooks contexts should run successfully (exit code 0)
    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, inputs["cmd"])()
    
    # the stage has custom outputs, check these
    if "outputs" in s["stage"]:
      pass

    # otherwise assume that we just ran some playbooks
    #  check that playbooks executed properly
    assert (len(outputs["playbook_results"].playbooks) > 0 and
      outputs["playbook_results"].statuscode == 0)


def test_model_lifecycle_w_analytics(model):
  for s in model_stages[model]:
    inputs = s["inputs"]
    inputs["cmd"] = s["stage"]

    # add the deploy_analytics=true flag
    if inputs["cmd"] == "init":
      inputs["extra_vars"]["deploy_analytics"] = "true"

    # reinstantiate EM each time as we are doing in ./bin/f5aws
    #  all playbooks contexts should run successfully (exit code 0)
    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, inputs["cmd"])()
    
    # the stage has custom outputs, check these
    if "outputs" in s["stage"]:
      pass

    # otherwise assume that we just ran some playbooks
    #  check that playbooks executed properly
    assert (len(outputs["playbook_results"].playbooks) > 0 and
      outputs["playbook_results"].statuscode == 0)
