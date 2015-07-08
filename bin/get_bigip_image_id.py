#get_aws_image_ids.py


"""
Tool to look up the ami-id of big-ip in the Amazon EC2 marketplace. 
Requires that aws executable is in the path.

Use examples

Look up the 11.6, Best, Hourly AMI. If multiple AMIs are returned with a version matching 11.6,
the latest matching version will be used.  
python get_aws_image_ids.py --region us-west-1 --license hourly --package best --throughput 1gbps --version 11.6

python get_aws_image_ids.py --region us-west-1 --license hourly --package best --throughput 1gbps --version 11.6 --oldest

BYOL images do not have defined throughput:
python get_aws_image_ids.py --region us-west-1 --license byol --package best  --version 11.6
"""

import sys
import json
import re
import argparse
import collections

import boto
import boto.ec2

REGIONS = [
	'ap-northeast-1',
	'ap-southeast-1',
	'ap-southeast-2',
	'eu-central-1',
	'sa-east-1',
	'us-east-1',
	'us-west-1',
	'us-west-2',
]

class ImageFinder(object):
	def __init__(self):
		pass

	def searchitem(self, keys, name):
		value = None
		for k in keys:
			match = re.search('({})'.format(k), name)
			if match:
				value = match.group(1)
				break
		return value

	def getImagesForRegion(self, region):
		"""
			Takes the name of an amazon region and retrieves a list of all
			images published by F5 for this region. 
			Formats a return object
		"""

		#get all the images
		arg_s = ['aws', 'ec2', 'describe-images',
		  '--region', region, '--filter',
		  'Name=name,Values=\'F5*\'', '--output=json']
		
		conn = boto.ec2.connect_to_region(region)
		images = conn.get_all_images(filters={'name':'F5*'})

		#dimensions
		packages = ['good', 'better', 'best']
		throughputs = ['[0-9]+gbps', '[0-9]+mbps']
		licenses = ['byol', 'hourly']
		versions = [
		  '[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+[.][0-9]+[.][0-9]+[-hf]*[0-9]*', # 11.6.0.1.0.403-hf1
		  '[0-9]+[.][0-9]+[.][0-9]+[-][0-9]+[.][0-9]+[-hf]*[0-9]*' # 11.4.1-649.0-hf5
		]

		structured = []
		for i in images:
			try:
				image_name = i.name.lower()
				image_id = i.id.lower()

				license = self.searchitem(licenses, image_name)
				version = self.searchitem(versions, image_name)
				throughput = self.searchitem(throughputs, image_name)
				package = self.searchitem(packages, image_name)

				structured.append({
					'name': image_name,
					'id': image_id,
					'version': version,
					'package': package,
					'license': license,
					'throughput': str(throughput)})

			except Exception, e:
				print 'Failed processing image "{}". Will not be added to index. Error was {}'.format(image_name, e)

		return structured

	def find(self, **kwargs):
		images = self.getImagesForRegion(region=kwargs['region'])
		if kwargs['package'] is not None:
			images = [i for i in images if i['package'] == kwargs['package']]

		if kwargs['license'] is not None:
			images = [i for i in images if i['license'] == kwargs['license']]

		if kwargs['license'] == 'hourly' and kwargs['throughput'] is not None:
			images = [i for i in images if i['throughput'] == kwargs['throughput']]

		if kwargs['version'] is not None:
			images = [i for i in images if i['version'] is not None and
			re.match('^({})'.format(kwargs['version']), i['version'])]

		def byName_version(image):
			return image['version']

		return sorted(images, key=byName_version, reverse=kwargs['take_newest'])
			

parser = argparse.ArgumentParser(description='Get AMI Ids in AWS for F5 Networks.')
parser.add_argument('-r', '--region', metavar='R', required=False,
                   help='region name', default='us-east-1')
parser.add_argument('-p', '--package', metavar='P', required=False,
                   help='good, better, best', default=None)
parser.add_argument('-l', '--license', metavar='L', required=False,
                   help='byol, hourly', default=None)
parser.add_argument('-v', '--version', metavar='L', required=False,
                   help='11, 11.6, 11.6.2, etc - latest version is provided unless left as default', default=None)
parser.add_argument('-t', '--throughput', metavar='T', required=False,#choices=['25mbps', '200mbps', '1gbps'],
                   help='Must be one of 25mbps, 200mbps, 1gbps.  Ignored if license is provided as BYOL', default=None)
parser.add_argument('-o', '--oldest', dest='take_newest', action='store_false', default=True,
          		   help='Take the newest order when multiple images match same version')
parser.add_argument('-1', '--matchone', action='store_true', default=False,
          		   help='Take the newest order when multiple images match same version')
args = vars(parser.parse_args())

try:
	if args['matchone'] is True:
		print ImageFinder().find(**args)[0]['id']
	else:
		print 'Found '
		for i in ImageFinder().find(**args):
			print i
except IndexError:
	# set the exit code so that ansible knows we have failed
	sys.exit('No images found')




