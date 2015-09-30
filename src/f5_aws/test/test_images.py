import pytest
import random
import boto
import sys
import json
import yaml

from f5_aws.config import Config
from f5_aws import image_finder, utils
from test_helpers import Region

config = Config().config
regions = config['regions']
#regions = ['us-west-1']

# scope=module => this setup function will be run once before 
#  executing all the test methods in this module
@pytest.fixture(scope="function", params=regions)
def testenv(request):
    testenv = dict()

    testenv['region'] = Region(request.param)
    testenv['region'].createVpc()
    testenv['region'].createSubnet()
    testenv['region'].createKeyPair()

    # define a finalizer which will be run to teardown
    #  the text fixture after all dependent tests
    #  have been run 
    def fin():
        testenv['region'].deleteAll()  
    request.addfinalizer(fin)

    return testenv
    

# Proper size, image, and virtualization type. We should
#  be able to pass this test, which means we are able to launch 
#  the image. 
# ...just a sanity check that our tests our working
# def test_working_image_conditions(testenv):
#   assert utils.touchImage(
#       region=testenv['region'].region_name,
#       keyName=testenv['region'].key_name,
#       subnetId=testenv['region'].subnet_id,
#       vpcId=testenv['region'].vpc_id,
#       imageId='ami-4c7a3924',
#       instanceType='t1.micro',
#       ) 

# # this image won't launch because of a mismatch between 
# #  the image virtualization type (hvm) and the ami definition
# # ...just a sanity check that our tests our working
# def test_broken_image_conditions(testenv):
#   assert not utils.touchImage(
#       region=testenv['region'].region_name,
#       keyName=testenv['region'].key_name,
#       subnetId=testenv['region'].subnet_id,
#       vpcId=testenv['region'].vpc_id,
#       imageId='ami-767a391e',
#       instanceType='t1.micro')

def validate_linux_image(testenv, host_type):
    """
    Here we read from our defaults settings files and playbook
    definitions to get the instance type and ami ids that we 
    will launch.  Its possible that a user chooses a different
    instance type, in which case this test will be meaningless, 
    but it is okay for most usage scenarios. 
    """

    # get the ami id for this type of host working region
    cft = json.loads(open(config['install_path']+
        '/roles/infra/files/'+host_type+'.json', 'r').read())
    image_id = cft['Mappings']['AWSRegionArch2AMI'][testenv['region'].region_name]['AMI']

    # get the default instance type for this type of host
    defaults = yaml.load(open(config['install_path']+
        '/roles/inventory_manager/defaults/main.yml'))
    instance_type = defaults[host_type+'_instance_type']

    return utils.touchImage(
        imageId=image_id,
        instanceType=instance_type,
        region=testenv['region'].region_name,
        vpcId=testenv['region'].vpc_id,
        keyName=testenv['region'].key_name,
        subnetId=testenv['region'].subnet_id)

def validate_bigip_image(testenv, host_type):
    """
    Similar to validate_linux_image, but here we are 
    specifically testing the ability to launch BIG-IP images.
    """
    # we can get all information from the defaults file, assume the user will use these
    defaults = yaml.load(open(config['install_path']+
        '/roles/inventory_manager/defaults/main.yml'))

    # get the ami id
    module_args = {
        'instance_type': defaults[host_type+'_instance_type'],
        'throughput': defaults[host_type+'_license_throughput'],
        'package': defaults[host_type+'_license_package'],
        'license': defaults[host_type+'_license_model'],
        'version': defaults[host_type+'_version'],
        'region': testenv['region'].region_name
    }
    image_id = image_finder.BigIpImageFinder().find(**module_args)[0]['id']

    return utils.touchImage(
        imageId=image_id,
        instanceType=defaults[host_type+'_instance_type'],
        region=testenv['region'].region_name,
        vpcId=testenv['region'].vpc_id,
        keyName=testenv['region'].key_name,
        subnetId=testenv['region'].subnet_id)

# runs once per region
def test_region(testenv):
    assert validate_linux_image(testenv, 'client')
    assert validate_linux_image(testenv, 'apphost')
    assert validate_bigip_image(testenv, 'bigip')
    assert validate_bigip_image(testenv, 'gtm')
