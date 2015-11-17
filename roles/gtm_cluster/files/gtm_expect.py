#!/usr/bin/env python

#############
# Quick and dirty expect script to workaround gtm_add and bigip_add interactive shell scripts 
# Currently catered to AWS environments where ssh key is required 
# Note: Currently investigating intermitent issue where bigip_add 
#       fails on some first runs.
#       Workaround: Just run playbook again. 
#############

import sys
import time
import pexpect

# SOME VARIABLES
MY_TIMEOUT=45
SSH_NEWKEY = 'Are you sure you want to continue connecting'

# TO DO: use optparse instead 
user = sys.argv[1]
host = sys.argv[2]
command = sys.argv[3]
peer_user = sys.argv[4]
peer_host = sys.argv[5]
password = sys.argv[6]

# + add debug flag 
# print "user: " + user
# print "host: " + host 
# print "command: " + command
# print "peer_user: " + peer_user
# print "peer_host: " + peer_host
# print "password: " + password

# QUICK VALIDATION
if host == peer_host:
  print "Exiting. Not running as target and destination are the same"
  sys.exit()


print "Logging on via ssh to : " + user + "@" + host
conn = pexpect.spawn("ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null " +  user + "@" + host)

match_value = conn.expect([SSH_NEWKEY, '[Pp]assword:', '\(tmos\)#', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
time.sleep(1)
#print "match_value = " + str(match_value)
if match_value == 0:
    print "Matched new key warning"
    conn.sendline ( "yes" )
if match_value == 1:
    #Not expected in AWS as SSH Key auth is used but keeping as reference/placeholder
    print "Matched Password prompt. Sending Password"
    conn.sendline ( password )
if match_value == 2:
    print "Matched TMSH prompt"
time.sleep(1)

if match_value != 2:
   #Assume we moved past key warning or password prompt
   conn.expect('\(tmos\)#', timeout=MY_TIMEOUT)

###### NOW RUN ACTUAL BIGIP_ADD OR GTM_ADD CMDS ##########
#SOL14495: The bigip_add and gtm_add scripts now accept a user name
print "Matched prompt. Now adding bigip peer with command \"run gtm " + command + " -a " + peer_user + "@" + peer_host + "\"";
conn.sendline("run gtm " + command +  " -a " + peer_user + "@" + peer_host)

# Handle gtm_add specific output
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
    print "Matched Password prompt. Most likely from subsequent run. Sending Password"
    conn.sendline ( password )

# SUCCESS == "==> Done <=="
match_value = conn.expect(['==> Done <==', '\(tmos\)#', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
if match_value == 0:
   print "Received \"==> Done <==\" : " +  "command " + command + " successful"
if match_value == 1:
   print "Received tmsh unexpected output (tmsh prompt). Need to check results"
   sys.exit()  
   
conn.sendline ('exit')
