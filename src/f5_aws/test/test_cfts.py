# use the boto api to test all the cfts
# which will be used to deploy ec2/vpc resources


import os
import sys
import boto
import boto.cloudformation
import pytest

from f5_aws.config import Config

config = Config().config
region_for_tests = config['regions'][0]

# dynamically get the cfts we want to test
local_cft_path = '/roles/infra/files/'
cfts = [(config['install_path'] + local_cft_path + f) for f in os.listdir(config['install_path']+local_cft_path)]

# scope=module => this setup function will be run once before 
#  executing all the test methods in this module
@pytest.fixture(scope="module", params=cfts)
def testenv(request):
    testenv = dict()
    testenv['cf_conn'] = boto.cloudformation.connect_to_region(region_for_tests)
    testenv['cft'] = request.param
    return testenv

def test_cft(testenv):
	template_loc = '' + testenv['cft']
	content = open(template_loc,'r').read()
	testenv['cf_conn'].validate_template(template_body=content)
	
	# if we got to hear, boto did not throw an exception
	assert True