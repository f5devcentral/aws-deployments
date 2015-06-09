# aws-deployments
## Deployment examples for F5's BIG-IP platform in AWS

#### About

f5aws is a tool for deploying F5 BIG-IP in various possible architectures within an AWS EC2 Virtual Private Cloud.

This tool is not made for production usage. Rather the goal is to allow users to evaluate the deployment architectures which best fit their application model.

Further, this library shows how BIG-IP can be orchestrated using open-source configuration management and workflow engines like Ansible.  These examples demonstrate the programmable APIs available from TMOS, include TMSH, iControlSoap, and iControlRest.

These examples are provided in order to demonstrate how BIG-IP can be used to manage the availability, performance, and security of applications running in AWS and other public cloud environments.


As of now, these deployment models are:
-standalone-per-zone


### Setup:
1) Download this code somewhere to your system

2) Per python boto module requirements, create ~/.aws folder with correct contents
(http://boto.readthedocs.org/en/latest/boto_config_tut.html).

i.e.: in ~/.aws/credentials

```
[default]
aws_access_key_id = <my access key>
aws_secret_access_key = <my secret key>
```


3) Create ~/.f5aws with the following contents

```
# location of top-level f5aws project directory
install_path: 'path to your install'
```

4) Install the project requirements, i.e.:


```pip install requirements.txt```

5) Fix the hardcoded AMI IDs in 
./roles/infra/tasks/deploy_bigip.yml (make this the AMI of BIG-IP hourly in the region where you are deploying)
./roles/infra/files/apphosts.yml (this will make sure you have the correct ECS optimized compute host for your application containers)


### Usage:

1) To create a new environment, use the init.yml playbook with the inventory provided as part of this repository. 
This will initialize the set of inventory and ansible variables necessary for deployment. After execution of this playbook, inspect '~/vars/f5aws/env/<b>env_name</b>'
 
 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "eu-west-1", "key_name": "mutzel-kp-eu-west-1", "zones": ["eu-west-1a","eu-west-1b"],"bigip_rest_password": "****"}'```

2) Deploy and manage the environment you instantiated in step 1: 

```./bin/f5aws deploy <your env>```

3) When you are done, just teardown the environment:

```./bin/f5aws teardown <your env>```

4) At any time, you can list all the deployments which are under management:

```./bin/f5aws list```

5) At any time, you can list all the deployments which are under management:

```./bin/f5aws describe <your env>```
