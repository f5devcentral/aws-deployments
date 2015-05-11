# aws-deployments
## Deployment examples for F5's BIG-IP platform in AWS

This repository contains a tool for deploying in various possible application architectures within AWS/

These examples are provided in order to demonstrate how BIG-IP can be used to manage the availability, performance, and security of applications running in AWS and other public cloud environments. 


### Ansible roles found in this playbook.  These are listed in the order in which they are deployed

###### infra: 
Deploys and manages infrastructure on which BIG-IP and applications are deployed.  This role can deploy BIG-IP virtual devices and application services in a number of deployment models.  For a listed of these deployment models, see ./roles/infra/files/

	As of now, these deployment models are:
		-standalone-bigip-per-zone
		-clustered-bigips-per-zone (not implemented)
		-clustered-bigips-within-single-zone (not implemented)
		-cluster-spanned-across-two-az (not implemented)

###### bigip_system:
Manages BIG-IP configuration at a global level, including user accounts, trust certifications, and behavioral setttings. 

###### bigip_cluster: 
Manages clustering of BIG-IP virtual devices as required by the deployment model. 

###### bigip_app: 
Deploys load balancing, security, and network traffic policies onto BIG-IP for deployed applications. 

###### docker_base:
This role ensures that the host on which we intend to run docker applications is docker-ready.

###### app:
This role deploys a simple application we have developed for traffic testing. 
The specific number of applications are deployed on a per-AZ basis.  Based on parameters, these application instances are either provisioned as pool member resources for BIG-IP devices in each availability zone, or only for device in the zone in which they are deployed. 

### Usage:

1) To create a new environment, use the init.yml playbook with the inventory provided as part of this repository. 
This will initialize the set of inventory and ansible variables necessary for deployment. After execution of this playbook, inspect '~/vars/<b>env_name</b>/'
 ```ansible-playbook ./playbooks/init.yml -i ./inventory/hosts --extra-vars '{"env_name":"<b>env_name</b>", "deployment_model": "standalone-per-zone", "region": "eu-west-1", "key_name": "mutzel-kp-eu-west-1", "zones": ["eu-west-1a","eu-west-1b"]}'```

2) Deploy and manage the environment from step 1, this time, specificy the inventory that is environment specific: 
```ansible-playbook ./playbooks/deploy.yml -i ~/vars/<b>env_name</b>```

