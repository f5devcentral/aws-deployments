# aws-deployments
## Deployment examples for F5's BIG-IP platform in AWS

#### About

f5aws is a tool for deploying F5 BIG-IP in various possible architectures within an AWS EC2 Virtual Private Cloud.

This tool is not made for production usage. Rather the goal is to allow users to evaluate the deployment architectures which best fit their application model.

Further, this library shows how BIG-IP can be orchestrated using open-source configuration management and workflow engines like Ansible.  These examples demonstrate the programmable APIs available from TMOS, include TMSH, iControlSoap, and iControlREST.

These examples are provided in order to demonstrate how BIG-IP can be used to manage the availability, performance, and security of applications running in AWS and other public cloud environments.


As of now, these deployment models are:

-standalone-per-zone


### Install/Setup:
1) Download this code somewhere to your system

2) Setup boto per requirements, i.e. create ~/.aws folder with correct contents
(http://boto.readthedocs.org/en/latest/boto_config_tut.html):

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


### Usage:

1) To create a new environment, use the init.yml playbook with the inventory provided as part of this repository. 
This will initialize the set of inventory and ansible variables necessary for deployment. After execution of this playbook, inspect '~/vars/f5aws/env/<b>env_name</b>'.  The full_key_path parameter may include a . extension (e.g. ".pem").  You must choose the availability zones in which you want to deploy. 
 
 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "eu-west-1", "full_key_path": "/full/path/to/your/key", "zones": ["eu-west-1a","eu-west-1b"],"bigip_rest_password": "****"}'```

 Note that the length of list passed to the "zones" variable must not strictly be 2.  This is also possible:

 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "eu-west-1", "full_key_path": "/full/path/to/your/key", "zones": ["eu-west-1a","eu-west-1b", "eu-west-1c"],"bigip_rest_password": "****"}'```

So you can deploy a standalone via: 

 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "eu-west-1", "full_key_path": "/full/path/to/your/key", "zones": ["eu-west-1c"],"bigip_rest_password": "****"}'```

2) Deploy and manage the environment you instantiated in step 1: 

```./bin/f5aws deploy <your env>```

3) When you are done, just teardown the environment:

```./bin/f5aws teardown <your env>```

4) At any time, you can list all the deployments which are under management:

```./bin/f5aws list```

5) List additional details about a specific environment:

```./bin/f5aws describe <your env>```
