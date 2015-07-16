#!/bin/bash

# install the necessary python dependencies
/usr/local/lib/python2.7.9/bin/virtualenv -p /usr/local/lib/python2.7.9/bin/python2.7 venv
source venv/bin/activate
pip install -r requirements.txt


