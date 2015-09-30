import re
import os
import sys
import stat
import json
import yaml
import time
import datetime

from f5_aws.config import Config
from f5_aws.utils import convert_str
from f5_aws.exceptions import ExecutionError, ValidationError, LifecycleError

# make our config global
config = Config().config

# ansible stuff
import ansible.playbook
import ansible.constants
from ansible import errors
from ansible import callbacks
from ansible import utils
from ansible.color import ANSIBLE_COLOR, stringc
from ansible.callbacks import display


def hostcolor(host, stats, color=True):
  if ANSIBLE_COLOR and color:
    if stats['failures'] != 0 or stats['unreachable'] != 0:
      return "%-37s" % stringc(host, 'red')
    elif stats['changed'] != 0:
      return "%-37s" % stringc(host, 'yellow')
    else:
      return "%-37s" % stringc(host, 'green')
  return "%-26s" % host

def colorize(lead, num, color):
  """ Print 'lead' = 'num' in 'color' """
  if num != 0 and ANSIBLE_COLOR and color is not None:
    return "%s%s%-15s" % (stringc(lead, color),
      stringc("=", color), stringc(str(num), color))
  else:
    return "%s=%-4s" % (lead, str(num))

class PlaybookExecution(object):
  """
    This class is used to execute a set of ansible playbooks
      included in ./playbooks.
    Playbooks are executed using the run method, which reloads the
    inventory between each playbook.  This is slightly different than the
    way that ansible-playbook command typically handles things.  It only loads
    the inventory once for a set of playbooks. 
  """
  config = config

  def __init__(self, playbooks, settings, inventory_path, options, extra_vars):
    
    self.inventory_path=inventory_path
    self.options=options
    self.extra_vars=extra_vars

    self.playbooks = playbooks
    self.runtime = 0 #seconds

  def run(self):
    """
      This is a modified version of the function used within ansible-playbook.
      playbooks. See top of file. 
    """

    tstart = time.time()

    # get the absolute path for the playbooks
    self.playbooks = [
      '{}/playbooks/{}'.format(config['install_path'], pb) for pb in self.playbooks]

    # Ansible defaults carried over from `ansible-playbook`.  Changes these
    # shouldn't be necessary since all R/W is done within *this* users
    # directory.
    sshpass = None
    sudopass = None
    su_pass = None
    vault_pass = None

    for playbook in self.playbooks:
      if not os.path.exists(playbook):
        raise errors.AnsibleError(
          "the playbook: %s could not be found" % playbook)
      if not (os.path.isfile(playbook) or stat.S_ISFIFO(os.stat(playbook).st_mode)):
        raise errors.AnsibleError(
          "the playbook: %s does not appear to be a file" % playbook)

    for playbook in self.playbooks:
      display("Running playbook: %s" %
          playbook, color='green', stderr=False)

      stats = callbacks.AggregateStats()
      playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
      runner_cb = callbacks.PlaybookRunnerCallbacks(
        stats, verbose=utils.VERBOSITY)
      inventory = ansible.inventory.Inventory(
        self.inventory_path, vault_password=vault_pass)

      if len(inventory.list_hosts()) == 0:
        raise errors.AnsibleError("provided hosts list is empty")

      pb = ansible.playbook.PlayBook(
        playbook=playbook,
        module_path=self.options.module_path,
        inventory=inventory,
        forks=self.options.forks,
        remote_user=self.options.remote_user,
        remote_pass=sshpass,
        callbacks=playbook_cb,
        runner_callbacks=runner_cb,
        stats=stats,
        timeout=self.options.timeout,
        transport=self.options.connection,
        sudo=self.options.sudo,
        sudo_user=self.options.sudo_user,
        sudo_pass=sudopass,
        extra_vars=self.extra_vars,
        check=self.options.check,
        diff=self.options.diff,
        su=self.options.su,
        su_pass=su_pass,
        su_user=self.options.su_user,
        vault_password=vault_pass,
        force_handlers=self.options.force_handlers
      )

      failed_hosts = []
      unreachable_hosts = []

      try:
        pb.run()

        hosts = sorted(pb.stats.processed.keys())
        display(callbacks.banner("PLAY RECAP"))
        playbook_cb.on_stats(pb.stats)

        for h in hosts:
          t = pb.stats.summarize(h)
          if t['failures'] > 0:
            failed_hosts.append(h)
          if t['unreachable'] > 0:
            unreachable_hosts.append(h)

        retries = failed_hosts + unreachable_hosts

        if len(retries) > 0:
          filename = pb.generate_retry_inventory(retries)
          if filename:
            display(
              "     to retry, use: --limit @%s\n" % filename)

        for h in hosts:
          t = pb.stats.summarize(h)

          display("%s : %s %s %s %s" % (
            hostcolor(h, t),
            colorize('ok', t['ok'], 'green'),
            colorize('changed', t['changed'], 'yellow'),
            colorize('unreachable', t['unreachable'], 'red'),
            colorize('failed', t['failures'], 'red')),
            screen_only=True
          )

          display("%s : %s %s %s %s" % (
            hostcolor(h, t, False),
            colorize('ok', t['ok'], None),
            colorize('changed', t['changed'], None),
            colorize('unreachable', t['unreachable'], None),
            colorize('failed', t['failures'], None)),
            log_only=True
          )

        print ""
        tend=time.time()
        self.runtime = tend-tstart

        if len(failed_hosts) > 0:
          self.statuscode = 2
          return

        if len(unreachable_hosts) > 0:
          self.statuscode = 3
          return

        self.statuscode = 0

      except errors.AnsibleError, e:
        display("ERROR: %s" % e, color='red')
        self.statuscode = 1
        return

    self.statuscode = 0


  def print_playbook_results(self):
    if self.statuscode == 0:
      display_color = 'green'
    else:
      display_color = 'red'
    display("Ran playbooks {}. \n Total time was {}".format(self.playbooks,
      datetime.timedelta(seconds=self.runtime)), color=display_color)
    

class EnvironmentManager(object):
  config=config
  def __init__(self, args):
    self.options=args
    self.extra_vars = {}    

    # pass along our project variables to ansible
    # some playbooks will need access keys and passwords during runtime
    for v in config['required_vars']:
      self.extra_vars[v] = config[v]

    # cloudformation templates will need just the key name, without any
    # extension
    self.extra_vars['ssh_key_name'] = config[
      'ssh_key'].split('/')[-1].split('.')[0]

    if getattr(self.options, 'env_name', None) is not None:
      self.extra_vars['env_name'] = self.options.env_name

    # Since we have forked and modified ansible-playbook 
    #  we have copied over many of these default variables.
    #  some of the options have been disabled due to unknown
    #  dependency changes we may have introduced.
    
    self.options.forks = ansible.constants.DEFAULT_FORKS
    self.options.module_path = ansible.constants.DEFAULT_MODULE_PATH
    self.options.remote_user = ansible.constants.DEFAULT_REMOTE_USER
    self.options.timeout = ansible.constants.DEFAULT_TIMEOUT
    self.options.connection = ansible.constants.DEFAULT_TRANSPORT
    self.options.sudo = ansible.constants.DEFAULT_SUDO
    self.options.sudo_user = None
    self.options.su = ansible.constants.DEFAULT_SU
    self.options.su_user = ansible.constants.DEFAULT_SU_USER
    self.options.check = False
    self.options.diff = False  
    self.options.force_handlers = False
    self.options.flush_cache = False
    self.options.listhosts = False
    self.options.listtasks = False
    self.options.syntax = False

    # the first inventory just contains a local host to run the init playbook
    self.proj_inventory_path = config['install_path'] + '/inventory/hosts'
    # the second inventory is specific to this deployment
    self.env_inventory_path = '%s/%s/inventory/hosts' % (
      config['env_path'], self.options.env_name)

  def init(self):
    """
    To instantiate a new environment, we create a set
    of inventory files for that environment. 

    See individual playbooks for more info. 
    """

    # additional options which need to be processed with the init command
    for extra_vars_opt in self.options.extra_vars:
      self.extra_vars = utils.combine_vars(self.extra_vars,
                        utils.parse_yaml(extra_vars_opt))

    # basic string checking to prevent failures later in playbook
    if not re.match('^[a-zA-z]{1}[a-zA-Z0-9-]*', self.options.env_name):
      raise ValidationError(
        'The environment name must match the following\
  regexp: "[a-zA-z]{1}[a-zA-Z0-9-]*" ')

    # check to make sure this inventory does not already exist
    if (os.path.isdir((config['env_path'] + self.options.env_name)) and not
      self.options.force):
        raise ValidationError(
          'There is already an environment with name "%s".  Use -f, --force to \
  update the inventory variables for this environment. ' % self.options.env_name)

    # check that this is one of the working regions
    if self.extra_vars['region'] not in config['regions']:
      raise ValidationError(
          'Only the following regions are possible when using this tool due to \
availability of the ECS-optimized images used to run the Docker app: {}'.format(
          config['regions']))

    # TODO: validate images, eip and cloudformation limits?

    playbooks = ['init.yml']
    playbook_context = PlaybookExecution(
      playbooks, config, self.proj_inventory_path, self.options, self.extra_vars)
    playbook_context.run()  

    return {'playbook_results': playbook_context, 'env': self}

  def deploy(self):

    # make sure the environment has been initialized
    envs = EnvironmentManager.get_envs()
    if not self.options.env_name in envs:
      raise LifecycleError('Environment "{}" does not exist.  Has it been initialized?'.format(
        self.options.env_name))

    playbooks = [
      'deploy_vpc_cft.yml',
      'deploy_az_cft.yml',
      'deploy_bigip_cft.yml',
      'deploy_gtm_cft.yml',
      'deploy_app_cft.yml',
      'deploy_client_cft.yml',
      'deploy_app.yml',
      'deploy_bigip.yml',
      'cluster_bigips.yml',
      'deploy_apps_bigip.yml',
      'deploy_gtm.yml',
      'deploy_apps_gtm.yml',
      'deploy_client.yml',
    ]

    playbook_context = PlaybookExecution(
      playbooks, config, self.env_inventory_path, self.options, self.extra_vars)
    playbook_context.run()  

    return {'playbook_results': playbook_context, 'env': self}

  def teardown(self):
    playbooks = ['teardown_all.yml']

    playbook_context = PlaybookExecution(
      playbooks, config, self.env_inventory_path, self.options, self.extra_vars)
    playbook_context.run()  

    return {'playbook_results': playbook_context, 'env': self}

  def start_traffic(self):
    playbooks = ['start_traffic.yml']

    playbook_context = PlaybookExecution(
      playbooks, config, self.env_inventory_path, self.options, self.extra_vars)
    playbook_context.run()  

    return {'playbook_results': playbook_context, 'env': self}

  def stop_traffic(self):
    playbooks = ['stop_traffic.yml']

    playbook_context = PlaybookExecution(
      playbooks, config, self.env_inventory_path, self.options, self.extra_vars)
    playbook_context.run()  

    return {'playbook_results': playbook_context, 'env': self}

  def remove(self):
    inventory, resources, statuses = self.get_environment_info()

    okToRemove = True
    stillExists = []
    for r in resources:
      if statuses[r]['state'] == 'deployed':
        okToRemove = False
        stillExists.append(r)

    if okToRemove is True:
      # uses the inventory included in this repository
      playbooks = ['remove.yml']
      print 'running {}'.format(playbooks)
      inventory_path = config['install_path'] + '/inventory/hosts'
      playbook_context = PlaybookExecution(
        playbooks, config, inventory_path, self.options, self.extra_vars)
      playbook_context.run()  
      return {'playbook_results': playbook_context, 'env': self}
    else:
      raise LifecycleError("""Cannot remove environment '%s' until all resources have been de-provisioned.
The following resources still exist: %s\n. 
Hint: try './bin/f5aws teardown %s'""" % (self.options.env_name, stillExists, self.options.env_name))

  @classmethod
  def get_envs(self):
    """
      Gets a list of all deployments
    """
    return os.listdir(config['env_path'])

  #### all over the below needs to get refactored....very ugly

  def get_environment_info(self):
    inventory = self.get_inventory()
    resources, statuses = self.get_latest_deploy_results(inventory)

    # clusters also show up in the statuses section, but we cannot
    #  print their status now, this causes them to show up under
    #  state = 'not deployed/error' for all models.  Avoiding this
    #  for now by removing them from the objects below
    for i, r in enumerate(resources):
      if 'cluster' in r:
        del statuses[r]
        del resources[i]

    return inventory, resources, statuses

  def display_basic_info(self):
    inventory, resources, statuses = self.get_environment_info()

    color = 'green'
    status = 'deployed'
    for k, v in statuses.items():
      try:
        if v['state'] != 'deployed':
          color = 'red'
          status = 'not deployed/error'
      except KeyError:
        color = 'red'
        status = 'not deployed/error'

    env_info = self.get_env_info(inventory)
    display(" - %s (%s)" % (self.options.env_name, status), color=color, stderr=False)
    for k in sorted(env_info, key=lambda key: key):
      display("  %s: %s" % (k, env_info[k]), color=color, stderr=False)

  def inventory(self):
    inventory, resources, statuses = self.get_environment_info()
    return inventory

  def resources(self):
    """
      Print information nicely about deployment resources to stdout
    """
    inventory, resources, statuses = self.get_environment_info()

    return resources, statuses

  def login_info(self):
    """
      Returns login information for each of the deployed host types.
      We need to extract the login information (user, ip address) froms
      slightly different information for each host type (gtm, bigip, client, etc...)
    """

    login_info = {}
    inventory, resources, statuses = self.get_environment_info()
   
    ansible_inventory = ansible.inventory.Inventory(
      self.env_inventory_path, vault_password=None)

    # login is a bit more custom - we want to show the login
    # information for a dynamic set of hosts - bigips, gtms, app hosts, and the client host
    # this information is compiled from the ansible inventory for this environment
    # and the output from the cloudformation stacks
    ip_map = {
      'gtm': 'ManagementInterfacePublicIp',
      'bigip': 'ManagementInterfacePublicIp',
      'apphost': 'WebServerInstancePublicIp',
      'client': 'ClientInstancePublicIp'
    }

    for host_type in ip_map.keys():
      try:
        group_name = host_type+'s'
        if inventory[group_name]:
          group_info = inventory[group_name]
          login_info[host_type] = {}

          # not very efficient...
          for resource_name, status in statuses.items():
            match = re.match(
              '^zone[0-9]+[/-]{}[0-9]+'.format(host_type), resource_name)

            if match:
              try:
                  resources = {}
                  key = group_info['vars'][
                      'ansible_ssh_private_key_file']
                  user = group_info['vars']['ansible_ssh_user']
                  ip = status['resource_vars'][ip_map[host_type]]
                  resources['ssh'] = 'ssh -i {} {}@{}'.format(
                    key, user, ip)
                  resources['https'] = 'https://{}'.format(ip)

                  if 'bigip' in resource_name:
                    resources['virtual_servers'] = self.collect_virtual_servers(resource_name)
                    resources['elastic_ips'] = self.collect_elastic_ips(resource_name)

                  if 'gtm' in resource_name:
                    resources['wideips'] = self.collect_wideips(resource_name)
                    resources['elastic_ips'] = self.collect_elastic_ips(resource_name)

                  login_info[host_type][self.host_to_az(
                  resource_name, ansible_inventory)] = resources
              except KeyError, e:
                pass
      except KeyError, e:
        pass

    return login_info

  def collect_resources(self, resource_name, fregex, fields, nested):
    r = []
    try: 
      searchDir = '%s/%s/' % (config['env_path'], self.options.env_name)
      files = os.listdir(searchDir)
      for fname in files:
        if re.match(fregex.format(resource_name), fname):
          with open(searchDir+fname) as data_file:
            content = json.load(data_file)
            if nested == False:
              r.append(dict(zip(fields, [content[x] for x in fields])))
            else:
              for i in content['items']:
                r.append(dict(zip(fields, [i[x] for x in fields])))
    except KeyError, e:
      print 'WARN: %s' % e
    return r

  def collect_elastic_ips(self, resource_name):
    return self.collect_resources(resource_name, '{}-vip-Vip[0-9]+.json', 
      ['eipAddress', 'privateIpAddress'], False)

  def collect_virtual_servers(self, resource_name):
    return self.collect_resources(resource_name, 'facts_{}.json', 
      ['name', 'destination'], True)

  def collect_wideips(self, resource_name):
    return self.collect_resources(resource_name, 'facts_{}.json', 
      ['name'], True)

  def host_to_az(self, resource_name, ansible_inventory):
    # traverse the ansible inventory to get the availability zone
    # for this host
    try:
      hostname = resource_name
      az = ansible_inventory.get_host(
        hostname).get_variables()['availability_zone']
      return '{}/{}'.format(az, resource_name)
    except:
      return ''

  def get_env_info(self, inventory):
    """Read some information about this @env from the inventory/hosts 
      file.  We do this by parsing the [all:vars] section.
    """

    env_info = {}
    env_info = inventory['all']['vars']

    # don't show the password in the output
    del env_info['env_name']

    return env_info

  def get_inventory(self):
    """
    Compiles group, host, and variable information using ansible API
    """

    ansible_inventory = ansible.inventory.Inventory(
      self.env_inventory_path, vault_password=None)

    inventory = {}
    for group, hosts in ansible_inventory.groups_list().items():
      inventory[group] = {
        'hosts': hosts,
        'vars': ansible_inventory.get_group(group).vars
      }

    return inventory

  def get_latest_deploy_results(self, inventory):
    """
      Attempts to read the output from tasks executed under a 'manager'
      host. 
    """

    hosts = [h for h in inventory['all']['hosts']]
    statuses = {}
    resources = []
    for m in hosts:
      # for each resource, we will get the results from
      #  most recent manager execution for that resource
      #resource_name = m[:-8]
      resource_name = m[:]

      resources.append(resource_name)
      try:
        fname = '{}/{}/{}.yml'.format(
          config['env_path'], self.options.env_name, m)
        with open(fname) as f:
          latest = yaml.load(f)
          statuses[resource_name] = getattr(self,
                            'state_' +
                            latest['invocation'][
                              'module_name'],
                            self.raise_not_implemented)(latest, True)

      except Exception as e:
        statuses[resource_name] = {'state': 'not deployed/error'}

    return resources, statuses

  def state_cloudformation(self, latest_result, show_resource_vars):
    """
      Returns the status of executed ansible cloudformation tasls
      from captured output. 
    """
    result = {}
    cf = convert_str(latest_result['invocation']['module_args'])
    
    # we need to handle 'present' and 'absent' situations differently
    if cf['state'] == 'present':
      result['stack_name'] = cf['stack_name']
      if show_resource_vars:
        result['resource_vars'] = latest_result['stack_outputs']
      if (latest_result['output'] == 'Stack CREATE complete' or
          latest_result['output'] == 'Stack is already up-to-date.'):
        result['state'] = 'deployed'
      else:
        result['state'] = 'deploy-error'
    else:  # state == 'absent'...
      # We need to deal with the case where the stack does not exist
      # in a particular fashion for the command line `descibe` and 
      # `list commands.
      if (latest_result.get('output', '') == 'Stack Deleted' or
          'does not exist' in latest_result.get('msg', '')):
        result['state'] = 'absent'
      else:
        result['state'] = 'teardown-error'

    return result

  def raise_not_implemented(*args, **kwargs):
    raise NotImplementedError()