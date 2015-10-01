#get_bigip_image_id.py
import os
import sys
import argparse
from f5_aws import image_finder

"""
Script to look up the ami-id of big-ip in the Amazon EC2 marketplace. 

Use examples

Look up the 11.6, Best, Hourly AMI. If multiple AMIs are returned with a version matching 11.6,
the latest matching version will be used.  
python get_bigip_image_id.py --region us-west-1 --license hourly --package best --throughput 1gbps --version 11.6

python get_bigip_image_id.py --region us-west-1 --license hourly --package best --throughput 1gbps --version 11.6 --oldest

BYOL images do not have defined throughput:
python get_bigip_image_id.py --region us-west-1 --license byol --package best  --version 11.6
"""

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
		print image_finder.BigIpImageFinder().find(**args)[0]['id']
	else:
		print 'Found '
		for i in image_finder.BigIpImageFinder().find(**args):
			print i
except IndexError:
	# set the exit code so that ansible knows we have failed
	sys.exit('No images found')




