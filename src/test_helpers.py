import random
import boto
import boto.ec2
import boto.vpc
from boto.exception import EC2ResponseError

def touchImage(region='', imageId='',
	keyName='', instanceType='', vpcId='',
	subnetId='', okayStatusCodes=[401]):

	try: 
		ec2_conn = boto.ec2.connect_to_region(region)
		print ec2_conn
		ec2_conn.get_image(image_id=imageId).run(
			instance_type=instanceType,
			key_name=keyName,
			subnet_id=subnetId,
			dry_run=True
			)
	except EC2ResponseError, e:
		
		status=int(e.status)

		if status not in okayStatusCodes:
			# e.reason == 'Unauthorized' => EULA needs to be accepted
			if int(e.status) == 401:
				print 'Error: Unauthorized to use this image {} in {}, \
	have the terms and conditions been accepted?'.format(
					imageId, region)
				return False

			# e.reason == 'Bad Request' => bad image launch conditions
			# for example:
			#	"The image id '[ami-4c7a3924]' does not exist"
			# 	"Virtualization type 'hvm' is required for instances of type 't2.micro'."
			elif int(e.status) == 400:
				print 'Error: Unable to launch image with params region={}, \
imageId={}, keyName={}, instanceType={}\r\n\
\tReason was: {}'.format(
						region, imageId, keyName, instanceType, e.message)
				return False

			# e.reason = 'Precondition Failed'
			# for example: 
			# 	Request would have succeeded, but DryRun flag is set.
			elif int(e.status) == 412:
				return True
			else: 
				raise e
				return False
	return True

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

