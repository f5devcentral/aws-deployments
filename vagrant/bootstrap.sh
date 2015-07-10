#!/bin/bash

#setup the bash file for first login
echo 'cd /aws-deployments' >> ~/.bash_profile
echo 'source venv/bin/activate' >> ~/.bash_profile

# install the necessary python dependencies
cd /aws-deployments
/usr/local/lib/python2.7.9/bin/virtualenv -p /usr/local/lib/python2.7.9/bin/python2.7 venv
source venv/bin/activate
pip install -r requirements.txt