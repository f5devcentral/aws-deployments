#!/usr/bin/python


#This would be module utils file

def bigip_argument_spec():
    return dict(
        hostname=dict(type='str', required=True),
        username=dict(type='str', aliases=['username', 'admin'], required=True),
        password=dict(type='str', aliases=['password', 'pwd'], required=True, no_log=True),
        timeout=dict(type='str',required=False, default=None),
        address_isolation=dict(default=False),
        strict_route_isolation=dict(default=False)
    )
