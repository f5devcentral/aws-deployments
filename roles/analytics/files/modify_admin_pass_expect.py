#!/usr/bin/env python

'''
Used to Get Around Password Prompt:
[ec2-user@ip-172-16-14-166 ~]$ sudo /opt/splunk/bin/splunk edit user admin -password NEWPASSWORD -auth admin:i-00cce3c5
The administrator requires you to change your password.
Please enter a new password:
Please confirm new password:
User admin edited.
'''

import sys
import time
import pexpect

MY_TIMEOUT=5
SSH_NEWKEY = 'Are you sure you want to continue connecting'

ssh_key = sys.argv[1]
user = sys.argv[2]
host = sys.argv[3]
old_password = sys.argv[4]
new_password = sys.argv[5]

# print "ssh_key: " + ssh_key
# print "user: " + user
# print "host: " + host 
# print "old_password: " + old_password
# print "new_password: " + new_password

print "Launching SSH session with command: ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i " + ssh_key + " " + user + "@" + host 
conn = pexpect.spawn("ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i " + ssh_key + " " + user + "@" + host)

match_value = conn.expect([SSH_NEWKEY, '$', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
time.sleep(1)

#print "match_value = " + str(match_value)
if match_value == 0:
    print "Matched new key warning"
    conn.sendline ( "yes" )
if match_value == 1:
    print "Matched CLI prompt. Sending Password Command"
    #print "sudo /opt/splunk/bin/splunk edit user admin -password '" + new_password + "' -role admin -auth admin:'" + old_password + "'"
    conn.sendline ( "sudo /opt/splunk/bin/splunk edit user admin -password '" + new_password + "' -role admin -auth admin:'" + old_password + "'"  )


match_value = conn.expect(['Please enter a new password:','Login failed', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
print "match_value = " + str(match_value)
time.sleep(1)

if match_value == 0:
    print "Matched Password prompt. Sending Password"
    conn.sendline ( new_password )
    match_value = conn.expect(['Please confirm new password:', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
    if match_value == 0:
        print "Matched Password Confirm. Resending Password"
        conn.sendline ( new_password )
        match_value = conn.expect(['User admin edited.', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
        if match_value == 0:
              print "User password successfully changed. Exiting"
              conn.sendline ( 'exit' )
elif match_value == 1:
	print "User login failed. Probably already set from previous run. Try confirming new password"
	#print "Sending: sudo /opt/splunk/bin/splunk edit user admin -password '" + new_password + "' -role admin -auth admin:'" + new_password + "'"
	conn.sendline ( "sudo /opt/splunk/bin/splunk edit user admin -password '" + new_password + "' -role admin -auth admin:'" + new_password + "'"  )
	match_value = conn.expect(['User admin edited.', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
	if match_value == 0:
	    print "Confirmed admin password successfully changed to new password. Exiting"
            conn.sendline ( 'exit' )
	else: 
	    print "Something is wrong. New Password is not set."
	    sys.exit(1)
else:
    print "Something is wrong. New Password is not set."
    sys.exit(1)


