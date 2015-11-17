import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()

setup(name='f5_aws',
      version='1.0.5',
      description='Code to deploy BIG-IP, network, and applications in AWS VPC',
      long_description=README,
      classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python",
        ],
      author='Chris Mutzel, Alex Applebaum',
      author_email='c.mutzel@f5.com, a.applebaum@f5.com',
      zip_safe=False,
      include_package_data=True,
      packages=find_packages()
      ) 
