#!/bin/bash

INSTALL_LOC=/aws-deployments

#setup the bash file for first login
echo 'cd /aws-deployments' >> ~/.bash_profile
echo 'source venv/bin/activate' >> ~/.bash_profile

# install the necessary python dependencies
cd $INSTALL_LOC
/usr/local/lib/python2.7.9/bin/virtualenv -p /usr/local/lib/python2.7.9/bin/python2.7 venv
source venv/bin/activate
pip install -r requirements.txt

# install redis
cd $INSTALL_LOC/library
wget http://download.redis.io/releases/redis-3.0.4.tar.gz
tar -xzvf redis-3.0.4.tar.gz 
mv redis-3.0.4 redis
cd ./redis
make



