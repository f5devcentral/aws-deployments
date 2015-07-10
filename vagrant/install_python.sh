#!/bin/bash

sudo apt-get update
sudo apt-get install -y aptitude
sudo apt-get install -y software-properties-common
sudo apt-get install -y build-essential
sudo apt-get install -y python-setuptools
sudo apt-get install -y python-dev
sudo apt-get install -y zlib1g-dev
sudo apt-get install -y libssl-dev
#Not necessarily needed for python compilation for this demo but for completeness
#https://renoirboulanger.com/blog/2015/04/upgrade-python-2-7-9-ubuntu-14-04-lts-making-deb-package/
sudo apt-get install -y gcc-multilib g++-multilib libffi-dev libffi6 libffi6-dbg python-crypto python-mox3 python-pil python-ply libbz2-dev libexpat1-dev libgdbm-dev dpkg-dev quilt autotools-dev libreadline-dev libtinfo-dev libncursesw5-dev tk-dev blt-dev libbz2-dev libexpat1-dev libsqlite3-dev libgpm2 mime-support netbase net-tools bzip2
sudo apt-get install -y git
#Python 2.7.9 specific
wget https://www.python.org/ftp/python/2.7.9/Python-2.7.9.tgz
tar xfz Python-2.7.9.tgz
cd Python-2.7.9/
./configure --prefix /usr/local/lib/python2.7.9 --enable-ipv6
sudo make
sudo make install
sudo sh -c "wget https://bootstrap.pypa.io/ez_setup.py -O - | /usr/local/lib/python2.7.9/bin/python"
sudo /usr/local/lib/python2.7.9/bin/easy_install pip
sudo /usr/local/lib/python2.7.9/bin/pip install virtualenv