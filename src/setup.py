import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()

setup(name='f5_aws',
      version='1.0.1',
      description='A basic service catalog for demonstrating the deployment of F5 in AWS',
      long_description=README,
      classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='Chris Mutzel, Alex Applebaum',
      author_email='c.mutzel@f5.com, a.applebaum@f5.com',
      keywords='web pyramid pylons',
      zip_safe=False,
      include_package_data=True,
      packages=find_packages(),
      # include_package_data=True,
      # zip_safe=False,
      # test_suite="service_catalog",
      entry_points="""\
      [paste.app_factory]
      main = service_catalog:main
      """,
      ) 
