# aws-deployments
## Deployment examples for F5's BIG-IP platform in AWS

This repository contains a tool for deploying in various possible application architectures within AWS/

These examples are provided in order to demonstrate how BIG-IP can be used to manage the availability, performance, and security of applications running in AWS and other public cloud environments. 


### Ansible roles found in this playbook.  These are listed in the order in which they are deployed

###### infra: 
Deploys and manages infrastructure on which BIG-IP and applications are deployed.  This role can deploy BIG-IP virtual devices and application services in a number of deployment models.  For a listed of these deployment models, see ./roles/infra/files/

	As of now, these deployment models are:
		-standalone-per-zone

###### bigip_system:
Manages BIG-IP configuration at a global level, including user accounts, trust certifications, and behavioral setttings. 

###### bigip_cluster: 
Manages clustering of BIG-IP virtual devices as required by the deployment model. 

###### bigip_app: 
Deploys load balancing, security, and network traffic policies onto BIG-IP for deployed applications. 

###### docker_base:
This role ensures that the host on which we intend to run docker applications is docker-ready.
README.md
###### app:
This role deploys a simple application we have developed for traffic testing. 
The specific number of applications are deployed on a per-AZ basis.  Based on parameters, these application instances are either provisioned as pool member resources for BIG-IP devices in each availability zone, or only for device in the zone in which they are deployed. 

### Setup:
1) Download this code somewhere to your system
2) Create ~/.f5aws with the following contents:

```
\---
install_path: '<path to your install>'
```


3) Install the project requirements, i.e.:

```pip install requirements.txt```

### Usage:

1) To create a new environment, use the init.yml playbook with the inventory provided as part of this repository. 
This will initialize the set of inventory and ansible variables necessary for deployment. After execution of this playbook, inspect '~/vars/f5aws/env/<b>env_name</b>'
 
 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "eu-west-1", "key_name": "mutzel-kp-eu-west-1", "zones": ["eu-west-1a","eu-west-1b"]}''```

2) Deploy and manage the environment you instantiated in step 1: 

```./bin/f5aws deploy <your env>```

3) When you are done, just teardown the environment:

```./bin/f5aws teardown <your env>```

4) At any time, you can list all the deployments which are under management:

```./bin/f5aws list```

5) At any time, you can list all the deployments which are under management:

```./bin/f5aws describe <your env>```
