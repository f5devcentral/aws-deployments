bigip_config.py README.md
=============

This directory includes a custom ansible module for provisioning 
TMOS objects using iControlRest.  The module provides an idempotent API.

Because bigip_config is included within bigip_network_general, it is 
available during all subsequent playbooks and provisioning steps. 
