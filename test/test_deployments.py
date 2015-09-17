import sys 
import pytest

sys.path.append('./src')
from f5_aws.config import Config
from f5_aws.utils import get_namespace
from f5_aws.runner import EnvironmentManager

config = Config().config
region_for_lifecyle_tests = config['regions'][0]
deployment_models = config['deployment_models']
#deployment_models = ['single-standalone']


# for each deployment model, we want to test the full lifecycle
# these are long running, full system tests

# at intermediate stages, we also want to check that we get back
#  certain content from back from the APIs

model_stages = {
  'single-standalone':
    [ {'stage': 'init',
        'inputs':
         {
            'env_name': 'ut-standalone',
            'extra_vars': ['{"deployment_model": "single-standalone", "region": "'+\
              region_for_lifecyle_tests+'", "zone": "'+region_for_lifecyle_tests+'b"}']
          }
      },
      # {'stage': 'deploy',
      #  'inputs':
      #   {
      #       'env_name': 'ut-standalone'
      #   }
      # },
      # # {stage: 'info'},
      # {'stage': 'teardown'},
      {'stage': 'remove',
       'inputs':
        {
            'env_name': 'ut-standalone'
        }
      }
    ],
  'single-cluster':
    [ {'stage': 'init',
        'inputs':
         {
            'env_name': 'ut-cluster',
            'extra_vars': ['{"deployment_model": "single-cluster", "region": "'+\
              region_for_lifecyle_tests+'", "zone": "'+region_for_lifecyle_tests+'b"}']
          }
      },
      # {'stage': 'deploy'},
      # #{stage: 'info'},
      # {'stage': 'teardown'},
      {'stage': 'remove',
       'inputs':
        {
            'env_name': 'ut-cluster'
        }
      }
    ],
  'cluster-per-zone':
    [ {'stage': 'init',
        'inputs':
         {
            'env_name': 'ut-cluster-per-zone',
            'extra_vars': ['{"deployment_model": "cluster-per-zone", "region": "'+\
              region_for_lifecyle_tests+'", "zones": ["'+region_for_lifecyle_tests+'b", "'+region_for_lifecyle_tests+'c"]}']
          }
      },
      # {'stage': 'deploy'},
      # #{stage: 'info'},
      # {'stage': 'teardown'},
      
      {'stage': 'remove',
       'inputs':
        {
            'env_name': 'ut-cluster-per-zone'
        }
      }
    ],
  'standalone-per-zone':
    [ {'stage': 'init',
        'inputs':
         {
            'env_name': 'ut-standalone-per-zone',
            'extra_vars': ['{"deployment_model": "standalone-per-zone", "region": "'+\
              region_for_lifecyle_tests+'", "zones": ["'+region_for_lifecyle_tests+'b", "'+region_for_lifecyle_tests+'c"]}']
          }
      },
      # {'stage': 'deploy'},
      # #{stage: 'info'},
      # {'stage': 'teardown'},
      
      {'stage': 'remove',
       'inputs':
        {
            'env_name': 'ut-standalone-per-zone'
        }
      }
    ], 
}

# scope=module => this setup function will be run once before 
#  executing all the test methods in this module
@pytest.fixture(scope="function", params=deployment_models) # params=config['regions'])
def model(request):

  return request.param

# can we run a deployment through the full lifecycle?
def test_model_lifecycle(model):
  for s in model_stages[model]:
    inputs = get_namespace(**s.get('inputs', {}))
    inputs.cmd = s['stage']

    # reinstantiate EM each time as we are doing in ./bin/f5aws
    #  all playbooks contexts should run successfully (exit code 0)
    em = EnvironmentManager(inputs)
    outputs = getattr(em, inputs.cmd)()
    
    # the stage has custom outputs, check these
    if 'outputs' in s['stage']:
      pass

    # otherwise assume that we just ran some playbooks
    #  check that playbooks executed properly
    assert (len(outputs['playbook_results'].playbooks) > 0 and
      outputs['playbook_results'].statuscode == 0)





