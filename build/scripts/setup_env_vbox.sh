#!/bin/bash -x

# This script is run from a Vagrantfile during startup 
# It contains the final steps to prepare the environment from the base build
# and update to the latest files (that change frequrently) from the git repo
# Some builders run commands at various user levels so have to clean up file permissions

# make sure the virtual environment is active
source venv/bin/activate

# set project home
PROJ_HOME=/home/vagrant/aws-deployments

# install the python module requirements
cd $PROJ_HOME
pip install -r requirements.txt

# install our specific modules
cd $PROJ_HOME/src
python setup.py install

# copy over the basic credential files
cp $PROJ_HOME/build/files/.f5aws ~/
cp -r $PROJ_HOME/build/files/.aws ~/

# setup the bash file for first login
if ! egrep activate ~/.bash_profile ; then echo 'source venv/bin/activate' >> $HOME/.bash_profile; fi
if ! egrep aws-deployments ~/.bash_profile ; then echo 'cd aws-deployments' >> $HOME/.bash_profile; fi

# attempt to set working directory in .f5aws to logged in user
sed -i.bak "s/home\/ubuntu/home\/`whoami`/" ~/.f5aws

# clean up permissions
sudo chown -R vagrant.vagrant ~/.*
sudo chown -R vagrant.vagrant ~/*


