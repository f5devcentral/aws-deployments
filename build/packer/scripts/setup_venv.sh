#!/bin/bash -x

# install the necessary python dependencies
#check that venv is installed and activate
/usr/local/lib/python2.7.9/bin/virtualenv -p /usr/local/lib/python2.7.9/bin/python2.7 venv

#Activate venv
source venv/bin/activate

#setup base requirements
pip install -r requirements.txt
pip install awscli
