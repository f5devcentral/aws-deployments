# settings.py

import os
import yaml

class Settings(dict):
  def __init__(self, __prog__):
    self['required_vars'] = ['install_path', 'ssh_key',
     'bigip_rest_user', 'bigip_rest_password',
     'f5_aws_access_key', 'f5_aws_secret_key']
    try:
      # load settings stored in a file configured by user
      global_vars_path = '~/.{}'.format(__prog__)
      fd = open(os.path.expanduser(global_vars_path), 'r')
      try:
        self.update((yaml.load(fd)))
        
      except yaml.YAMLError, e:
        raise Exception("Fatal YAML error while reading settings file in {}, \
  perhaps there is a syntax error in the file?\r\nThe error was {}".format(
          global_vars_path, e))
  
      for v in self['required_vars']:
        try:
          if v in self:
            pass
        except KeyError:
            raise Exception(
                'Required variable "{}" not found in {}'.format(v, global_vars_path))
  
      self['vars_path'] = os.path.expanduser(
        '~/vars/{}'.format(__prog__))
      self['lock_path'] = self['vars_path'] + '/lock/'
      self['env_path'] = self['vars_path'] + '/env/'
      self['bin_path'] = self['install_path'] + '/bin/'

      print 'hello'
  
      # make the /env/ directory if it does not exist
      os.makedirs(self['env_path'])
    except OSError:
      pass