bigip_system
=============

This role will configure general system settings such as:

- NTP
- DNS
- Syslog
- HTTP
- SSH
- SNMP
- Traffic Profiles (tcp, fastL4, etc.) that can be shared by all
- DB keys 
- Module Resource Provisioning (for generic modules like MGMT/AVR/etc.)
     Note: Other advanced modules like ASM, APM, GTM, should be probably be handled in a separate role
