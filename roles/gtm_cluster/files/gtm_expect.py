#!/usr/bin/env python

"""
Quick and dirty approach to clustering BIG-IP
  BIG-IP offers no API based approach to clustering that
  can be performed over REST/SOAP.  Instead we use expect scripts.
  a.applebaum@f5.com
"""

def debug_conn ( conn ):
   print "Before Match:"
   print conn.before
   print "After Match:"
   print conn.after
   print ""


import sys
import time
import pexpect
#import pexpect.pxssh as pxssh

#TODO: use optparse instead
user = sys.argv[1]
host = sys.argv[2]
command = sys.argv[3]
peer_user = sys.argv[4]
peer_host = sys.argv[5]
password = sys.argv[6]
print_debug = 0

if print_debug == 1:
   print "user: " + user
   print "host: " + host
   print "command: " + command
   print "peer_user: " + peer_user
   print "peer_host: " + peer_host
   print "password: " + password


if host == peer_host:
   print "Exiting. Not running as target and destination are the same"
   sys.exit()


MY_TIMEOUT = 30
SSH_NEWKEY = 'Are you sure you want to continue connecting'

print "SSH'ing to : " + user + "@" + host
conn = pexpect.spawn("ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null " +  user + "@" + host)

match_value = conn.expect([SSH_NEWKEY, '[Pp]assword:', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);
#print "match_value = " + str(match_value)
if print_debug == 1:
   debug_conn(conn)

time.sleep(1)
if match_value == 0:
    print "Matched new key warning"
    conn.sendline ( "yes" )
elif match_value == 1:
    print "Matched Password prompt. Sending Password"
    conn.sendline ( password )
time.sleep(1)

#Hopefully eventually get here
match_value = conn.expect('\(tmos\)#', timeout=MY_TIMEOUT)

if print_debug == 1:
   debug_conn(conn)

if match_value == 0:
    #bash prompt
    #conn.expect('~ #', timeout=MY_TIMEOUT)
    #SOL14495: The bigip_add and gtm_add scripts now accept a user name
    print "Matched tmsh prompt! Now adding bigip peer with command \"run gtm " + command + " -a " + peer_user + "@" + peer_host + "\"";
    conn.sendline("run gtm " + command +  " -a " + peer_user + "@" + peer_host)

if command == "gtm_add":
    conn.expect ('Are you absolutely sure you want to do this?')
    print "Confirming will wipe away this config and use peer GTM's config instead"
    conn.sendline ('y')
time.sleep(3);

#Otherwise will get a insecure key warning for the first attempt for either command
match_value = conn.expect([SSH_NEWKEY, pexpect.EOF, pexpect.TIMEOUT], timeout = MY_TIMEOUT)

if print_debug == 1:
   debug_conn(conn)

if match_value == 0:
    print "Matched new key warning"
    conn.sendline ( "yes" )

#Subsequent attempts will just get a password prompt
match_value = conn.expect([ '[Pp]assword:', pexpect.EOF, pexpect.TIMEOUT], timeout = MY_TIMEOUT)

if print_debug == 1:
   debug_conn(conn)

if match_value == 0:
    print "Matched Password prompt. Sending Password"
    conn.sendline ( password )

# Expect "==> Done <==" as sign of success
match_value = conn.expect(['==> Done <==', '\(tmos\)#', pexpect.EOF, pexpect.TIMEOUT], timeout=MY_TIMEOUT);

if print_debug == 1:
   debug_conn(conn)

if match_value == 0:
   print "Received \"==> Done <==\" : " +  "command " + command + " successful"
   print "exiting cleanly"
   sys.exit(0)
elif match_value == 1:
   print "Recived tmsh prompt? Really need to check results"
   sys.exit(1)
else:
   #anything else, fail
   sys.exit(1)
