import sys 
import boto
import boto.cloudformation

from boto.exception import BotoServerError

try:
	if len(sys.argv) != 3:
		sys.exit('Wrong number of input args!')
	cf_conn = boto.cloudformation.connect_to_region(sys.argv[1])
	if not cf_conn:
		sys.exit('Could not establish boto connection!')
	print cf_conn.describe_stacks(stack_name_or_id=sys.argv[2])[0].stack_status.upper()
	sys.exit()
except BotoServerError as e:
	# assume that this caught exception is because the stack does not exist
	# Example exception:
	# BotoServerError: 400 Bad Request
	# <ErrorResponse xmlns="http://cloudformation.amazonaws.com/doc/2010-05-15/">
	#   <Error>
	#     <Type>Sender</Type>
	#     <Code>ValidationError</Code>
	#     <Message>Stack with id mystack does not exist</Message>
	#   </Error>
	#   <RequestId>4b1e324d-1ea7-11e5-b8a7-c3a427ceaa91</RequestId>
	# </ErrorResponse>
	print 'ABSENT'
	sys.exit(0)
except Exception as e:
	sys.exit('Uncaught exception: %s' % e)



