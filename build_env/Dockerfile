############################################################
# Dockerfile to build F5 Demo container images
# Based on Ubuntu
############################################################

# Set the base image to Ubuntu
FROM ubuntu:14.04.2

# File Author / Maintainer
MAINTAINER Alex Applebaum a.applebaum@f5.com

RUN apt-get update && apt-get install -y \
    wget \
    tar \
    ca-certificates \
    git \
    bzip2 \
    aptitude \
    software-properties-common \
    build-essential \
    python-setuptools \
    python-dev \
    zlib1g-dev \
    libssl-dev 

# From libssl-dev down, not necessarily needed for python compilation for this demo but for python completeness
# https://renoirboulanger.com/blog/2015/04/upgrade-python-2-7-9-ubuntu-14-04-lts-making-deb-package/

RUN apt-get install -y \
    gcc-multilib \
    g++-multilib \
    libffi-dev \
    libffi6 \
    libffi6-dbg \
    python-crypto \
    python-mox3 \
    python-pil \
    python-ply \
    libbz2-dev \
    libexpat1-dev \
    libgdbm-dev \
    dpkg-dev \
    quilt \
    autotools-dev \
    libreadline-dev \
    libtinfo-dev \
    libncursesw5-dev \
    tk-dev \
    blt-dev \
    libbz2-dev \
    libexpat1-dev \
    libsqlite3-dev \
    libgpm2 \
    mime-support \
    netbase \
    net-tools
 
WORKDIR /tmp/

# Python 2.7.9 specific
RUN wget https://www.python.org/ftp/python/2.7.9/Python-2.7.9.tgz && \
    tar xfz Python-2.7.9.tgz && \
    rm Python-2.7.9.tgz && \
    cd Python-2.7.9 && \
    ./configure --prefix /usr/local/lib/python2.7.9 --enable-ipv6 && \
    make && \
    make install


# See: 
# https://hynek.me/articles/virtualenv-lives/
# https://glyph.twistedmatrix.com/2015/03/docker-deploy-double-dutch.html
# for why still running virtualevn in a container
RUN wget https://bootstrap.pypa.io/ez_setup.py -O - | /usr/local/lib/python2.7.9/bin/python && \
    /usr/local/lib/python2.7.9/bin/easy_install pip && \
    /usr/local/lib/python2.7.9/bin/pip install virtualenv virtualenvwrapper

WORKDIR /

#Copy requirements.txt from main aws-deployments directory (assumes docker image built from this git repo)
COPY requirements.txt /venv/requirements.txt

# install the necessary python dependencies
# http://stackoverflow.com/questions/20635472/using-the-run-instruction-in-a-dockerfile-with-source-does-not-work

RUN /bin/bash -c "/usr/local/lib/python2.7.9/bin/virtualenv -p /usr/local/lib/python2.7.9/bin/python2.7 venv && \
    source venv/bin/activate && \
    pip install -r /venv/requirements.txt"

CMD ["bash", "--rcfile", "venv/bin/activate"]

WORKDIR /aws-deployments
