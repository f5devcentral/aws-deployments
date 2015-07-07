#!/usr/bin/env python

import sys
import time
import pexpect
#import pexpect.pxssh as pxssh

user = sys.argv[1]
host = sys.argv[2]
command = sys.argv[3]
peer_user = sys.argv[4]
peer_host = sys.argv[5]
password = sys.argv[6]
# 
# print "user: " + user
# print "host: " + host 
# print "command: " + command
# print "peer_user: " + peer_user
# print "peer_host: " + peer_host
# print "password: " + password
# 

MY_TIMEOUT=15
SSH_NEWKEY = 'Are you sure you want to continue connecting'

print "SSH'ing to : " + user + "@" + host
conn = pexpect.spawn("ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null " +  user + "@" + host)
# 
# conn = pxssh.pxssh( options={
#                     "StrictHostKeyChecking": "no",
#                     "UserKnownHostsFile": "/dev/null"
#                     }
#                   )
#conn.login(host, user, password)

match_value = conn.expect([SSH_NEWKEY, '[Pp]assword:', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
time.sleep(1)
print "match_value =" + str(match_value)
if match_value == 0:
    print "Matched new key warning"
    conn.sendline ( "yes" )
if match_value == 1:
    print "Matched Password prompt. Sending Password"
    conn.sendline ( password )
time.sleep(1)
#tmsh prompt
conn.expect('\(tmos\)#', timeout=MY_TIMEOUT)
#bash prompt
#conn.expect('~ #', timeout=MY_TIMEOUT)
#SOL14495: The bigip_add and gtm_add scripts now accept a user name
print "Matched prompt. Now adding bigip peer with command \"run gtm " + command + " " + peer_user + "@" + peer_host + "\"";
conn.sendline("run gtm " + command +  " -a " + peer_user + "@" + peer_host)
if command == "gtm_add":
    conn.expect ('Are you absolutely sure you want to do this?')
    print "Confirming will wipe away this config and use peer GTM's config instead"
    conn.sendline ('y')
time.sleep(1);
match_value = conn.expect([SSH_NEWKEY, '[Pp]assword:', pexpect.EOF, pexpect.TIMEOUT], timeout = MY_TIMEOUT)
if match_value == 0:
    print "Matched new key warning"
    conn.sendline ( "yes" )
    conn.expect('[Pp]assword:', timeout = MY_TIMEOUT)
    print "Matched Password prompt. Sending Password"
    conn.sendline ( password )
if match_value == 1:
    print "Matched Password prompt. Sending Password"
    conn.sendline ( password )

conn.expect ('==> Done <==', timeout=MY_TIMEOUT)
print "command " + command + " successful"
conn.sendline ('exit')
