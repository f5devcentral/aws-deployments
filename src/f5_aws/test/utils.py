import random
import boto
import boto.ec2
import boto.vpc
from boto.exception import EC2ResponseError

class Region(object):
    def __init__(self, region):

        self.uid='ut_{}'.format(random.randint(1, 10000000000))
        self.region_name = region
        self.ec2_conn = boto.ec2.connect_to_region(region)
        self.vpc_conn = boto.vpc.connect_to_region(region)

        self.key_name = self.uid+'_kp' 
        
        self.vpc_id = ''
        self.vpc_name = self.uid+'_vpc'
        self.vpc_netmask = '10.0.0.0/24'

        self.subnet_id = ''
        self.subnet_name = self.uid+'_subnet'
        self.subnet_netmask = self.vpc_netmask

    def createVpc(self):
        self.vpc_id = self.vpc_conn.create_vpc(self.vpc_netmask).id

    def deleteVpc(self):
        self.vpc_conn.delete_vpc(self.vpc_id)

    def createSubnet(self):
        self.subnet_id = self.vpc_conn.create_subnet(self.vpc_id, self.subnet_netmask).id

    def deleteSubnet(self):
        self.vpc_conn.delete_subnet(self.subnet_id)

    def createKeyPair(self):
        self.keypair = self.ec2_conn.create_key_pair(self.key_name)

    def deleteKeyPair(self):
        self.ec2_conn.delete_key_pair(self.key_name)

    def deleteAll(self):
        self.deleteSubnet()
        self.deleteVpc()
        self.deleteKeyPair()

