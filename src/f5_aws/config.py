# config.py

import os
import yaml
  
from configobj import ConfigObj

class Config(object):
  def __init__(self):
    # our basic program variables
    self.config = ConfigObj('./conf/config.ini')
    
    # get user supplied variables
    self.config.merge(ConfigObj(os.path.expanduser(self.config['global_vars'])))

    # check that we got everything we need
    for v in self.config['required_vars']:
      if not v in self.config:
        raise Exception(
          'Required variable "{}" not found in {}'.format(v, self.config['global_vars']))
        
    self.config['vars_path'] = os.path.expanduser(
      '~/vars/{}'.format(self.config['prog']))
    self.config['lock_path'] = self.config['vars_path'] + '/lock/'
    self.config['env_path'] = self.config['vars_path'] + '/env/'
    self.config['bin_path'] = self.config['install_path'] + '/bin/'

    # make the /env/ directory if it does not exist
    try:
      os.makedirs(self.config['env_path'])
    except OSError:
      pass