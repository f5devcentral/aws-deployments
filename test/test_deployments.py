import sys 
import pytest

sys.path.append('../src')

from f5_aws.config import Config

config = Config().config