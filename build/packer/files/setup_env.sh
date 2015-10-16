#!/bin/bash -x

# make sure the virtual environment is active
source venv/bin/activate

# clone the latest code
git clone https://github.com/F5Networks/aws-deployments.git

# change into the directory
cd aws-deployments

# check out the sales_demo branch 
git fetch 
git checkout sales_demo

# install the python module requirements
pip install -r requirements.txt

# copy over the basic setup files
cp ./build/files/.f5aws ~/
cp -r ./build/files/.aws ~/
