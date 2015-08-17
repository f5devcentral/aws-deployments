# aws-deployments
## Deployment examples for F5's BIG-IP platform in AWS

#### About

f5aws is a tool for deploying F5 BIG-IP in various possible architectures within an AWS EC2 Virtual Private Cloud.

This tool is not made for production usage. Rather the goal is to allow users to evaluate the deployment architectures which best fit their application model.

Further, this library shows how BIG-IP can be orchestrated using open-source configuration management and workflow engines like Ansible.  These examples demonstrate the programmable APIs available from TMOS, include TMSH, iControlSoap, and iControlREST.

These examples are provided in order to demonstrate how BIG-IP can be used to manage the availability, performance, and security of applications running in AWS and other public cloud environments.


As of now, these deployment models are:<br>
-single-standalone (single big-ip and application server in one availability zone) <br>
-single-cluster (cluster of big-ips and application server in one availability zone) <br>
-standalone-per-zone (big-ips in multiple availability zones, fronted by a gtm in each AZ, application hosts in each AZ, and a host in the external subnet for traffic generation)<br>
-cluster-per-zone (big-ip clusters in multiple availability zones, fronted by gtm in each AZ, application hosts in each AZ, and a host in the external subnet for traffic generation)<br>

#### Support

This code is provided as is and should be used as a reference only.  It is not provided as a production-ready tool and F5 support will not field requests for this work.  


### Install/Setup:
1) Install Virtual Box and Vagrant 
Install virtual box (tested using 4.3.26)<br>
https://www.virtualbox.org/wiki/Downloads

Install vagrant (tested using 1.7.2)<br>
http://docs.vagrantup.com/v2/installation/

2) Clone this code to your desktop:<br>
```git clone https://github.com/F5Networks/aws-deployments.git```

3) Setup the virtualbox host with vagrant: <br>
```cd aws-deployments/vagrant```<br>
```vagrant up```

4) When prompted by the vagrant, choose network interface attached to the internet.

5) Once the virtual box has started, login to the machine:<br>
```vagrant ssh```

6) Edit/Copy (manually with VIM/Nano or SCP) your credentials and environment variables over to your vagrant guest:

- ~/.ssh/<your_aws_ssh_key>
- ~/.aws/credentials
- ~/.f5aws

An example of copying your your AWS SSH private key over to vagrant guest:


user1@desktop:demo $scp -P 2222 ~/.ssh/AWS-SSH-KEY.pem vagrant@127.0.0.1:~/.ssh/AWS-SSH-KEY.pem
Warning: Permanently added '[127.0.0.1]:2222' (RSA) to the list of known hosts.
vagrant@127.0.0.1's password:
AWS-SSH-KEY.pem            100% 1696     1.7KB/s   00:00



### Usage:

1) To create a new environment, use the 'init' command.
This will initialize the set of ansible variables necessary for deployment (known as an 'inventory'. After execution of this playbook, inspect '~/vars/f5aws/env/<b>env_name</b>'.


```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "single-standalone", "region": "us-east-1", "zone": "us-east-1b"}'```

```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "single-cluster", "region": "us-east-1", "zone": "us-east-1b" }'```


You can also try out a more complex deployment model ( complete with GTMs (up to 2 - one in each AZ) and a jmeter client to generate traffic) that can leverage multiple AZs. You must choose the availability zones in which you want to deploy. 
 
 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "us-east-1", "zones": ["us-east-1b"]}'```

 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "us-east-1", "zones": ["us-east-1b","us-east-1c"]}'```

 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "standalone-per-zone", "region": "us-east-1", "zones": ["us-east-1b","us-east-1c","us-east-1d"]}'```

or using clusters:

 ```./bin/f5aws init <your env> --extra-vars '{"deployment_model": "cluster-per-zone", "region": "us-east-1", "zones": ["us-east-1b","us-east-1c"]}' ```

NOTE: These have larger resource requirements (EIPs + CFTs) so you may need to increase your limits ahead of time.
 

2) Deploy and manage the environment you instantiated in step 1.  This creates all the resources associated with environment, including AWS EC2 hosts, a VPC, configuration objects on BIG-IP and GTM, and docker containers.  

```./bin/f5aws deploy <your env>```

3) When you are done, just teardown the environment:

```./bin/f5aws teardown <your env>```

4) At any time, you can list all the deployments which are under management:

```./bin/f5aws list```

5) List additional details about an environment via the info command, which has three subcommands:

- display login information for hosts deployed in ec2<br>
```./bin/f5aws info login <your env>```

- print the ansible inventory (dynamic inventory groups like bigips, apphosts, gtms, etc are not printed)<br>
```./bin/f5aws info inventory <your env>```

- print the status of deployed infrastructure and output from cloudformation stacks<br>
```./bin/f5aws info resources <your env>```

