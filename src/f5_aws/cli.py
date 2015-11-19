import json
import argparse

import ansible.utils
from ansible.callbacks import display

from f5_aws.config import Config
from f5_aws.exceptions import ExecutionError
from f5_aws.environment_manager import EnvironmentManager, EnvironmentManagerFactory

# make our config global
config = Config().config

def print_playbook_results(exec_results):
  if 'playbook_results' in exec_results:
    exec_results['playbook_results'].print_playbook_results()

def pretty_print(to_print):
  print json.dumps(to_print, indent=4, sort_keys=True)

def get_parser():
    """
      Define the various command line methods and arguments here. 
      For each command, implement a sub-parser. Later we will call
      the corrosponding method (e.g. init -> cli_init) and pass the 
      corrosponding argument values. 
    """
    parser = argparse.ArgumentParser(prog=config['prog'])
    parser.add_argument("-v", "--verbose", action="count", default=0,
      help="verbose mode (-vvv for more, -vvvv to enable connection debugging")
    subparsers = parser.add_subparsers(dest="cmd", help="sub-command help")

    parser_init = subparsers.add_parser("init",
      help="Create a new AWS deployment with F5 services.")
    parser_init.set_defaults(cmd="init")
    parser_init.add_argument("env_name",
      help="Name of the new environment to be created")
    parser_init.add_argument("-f", "--force", required=False,
      action="store_true", default=False,
      help="Use to update inventory variables for an existing environment")
    parser_init.add_argument("-e", "--extra-vars", required=True,
      dest="extra_vars", action="append",
      help="set additional variables as key=value or YAML/JSON", default=[])
    
    parser_deploy = subparsers.add_parser("deploy",
      help="Deploy EC2 resource and application services based on inventory files created using `init`.")
    parser_deploy.add_argument("env_name", metavar="ENVIRONMENT",
     type=str, help="Name of environment to be deployed/updated")
    parser_deploy.add_argument("-e", "--extra-vars", required=False,
     dest="extra_vars", action="append",
     help="set additional variables as key=value or YAML/JSON", default=[])

    parser_teardown = subparsers.add_parser("teardown",
      help="De-provision all resources in AWS EC2 for an environment created using `init`.")
    parser_teardown.add_argument("env_name", metavar="ENVIRONMENT",
      type=str, help="Name of environment to be de-provisioned. ")

    parser_list = subparsers.add_parser("list",
      help="List all deployments and corrosponding resource statuses.")

    parser_remove = subparsers.add_parser("remove",
      help="Remove all inventory files for an environment created using `init`.")
    parser_remove.add_argument("env_name", metavar="ENVIRONMENT",
      type=str, help="Name of environment to be deleted")

    parser_start_traffic = subparsers.add_parser("start_traffic",
      help="Begins jmeter client on client in a single availability zone")
    parser_start_traffic.add_argument("env_name", metavar="ENVIRONMENT",
      type=str, help="Name of environment to which jmeter client should run traffic")

    parser_stop_traffic = subparsers.add_parser("stop_traffic",
      help="Stops jmeter client ")
    parser_stop_traffic.add_argument("env_name", metavar="ENVIRONMENT",
      type=str, help="Name of environment")

    parser_info = subparsers.add_parser("info",
      help="Show resource variables along with environment information.")

    # multiple subparsers for the info command
    info_subparsers = parser_info.add_subparsers(
      dest="cmd", help="sub-command help")

    parser_inventory = info_subparsers.add_parser("inventory",
      help="Displays the ansible inventory associated with this environment. Dynamic inventory groups are not shown")
    parser_inventory.add_argument("env_name", metavar="ENVIRONMENT",
      type=str, help="Name of environment")

    parser_resources = info_subparsers.add_parser("resources",
      help="Shows hosts, associated resources and variables that are deployed via CloudFormation")
    parser_resources.add_argument("env_name", metavar="ENVIRONMENT",
      type=str, help="Name of environment")

    parser_login = info_subparsers.add_parser("login",
      help="Displays login information for deployed hosts (bigips, gtms, client, etc")
    parser_login.add_argument("env_name", metavar="ENVIRONMENT",
      type=str, help="Name of environment")

    return parser

class CLI(object):

  @staticmethod
  def init(args): 
    """
      Create the ansible inventory for the environment
        based on the deployment model and other variables
    """  
    exec_results = EnvironmentManager(args).init()
    print_playbook_results(exec_results)

    if ("playbook_results" in exec_results and 
      getattr(exec_results["playbook_results"], "statuscode", -1)) == 0:
      print ""
      print "The Ansible inventory for your environment has now been initialized.\
  Deploy the environment with the `deploy` command.\n"
      print "You can view the inventory for this environment in {}".format(
        exec_results['env'].env_inventory_path)

  @staticmethod
  def deploy(args):
    """
      Deploy an environment based on the set of inventory files 
      created by the 'init' command.
    """
    exec_results = EnvironmentManager(args).deploy()
    print_playbook_results(exec_results)

    try:
      # print the login information if the deployment was successful
      if exec_results["playbook_results"].statuscode == 0:
        print ""
        print "If you\'ve deployed a client, you can start traffic by \
  running:\n./bin/{} {} {}".format(
          config["prog"], "start_traffic", args.env_name)

        print "\nPrint login information along with the ansible \
  inventory using 'info' command, i.e. `info login`\n"
        print ""
    except KeyError: 
      pass

  @staticmethod
  def teardown(args):
    """
      Complete teardown of a deployed environment.
      Does not remove the environment inventory. 
    """
    exec_results = EnvironmentManager(args).teardown()
    print_playbook_results(exec_results)

  @staticmethod
  def remove(args):
    """
      Deletes all inventory files for a deployment from ~/vars/f5aws/env/<env name>
      This environment should already have been torn down using `teardown`
    """
    exec_results = EnvironmentManager(args).remove()
    print_playbook_results(exec_results)

    try:
      # print the login information if the deployment was successful
      if exec_results["playbook_results"].statuscode == 0:
        print ""
        display(" The environment '{}' has been successfully removed".format(args.env_name),
          color="green", stderr=False)
    except KeyError, e:
      raise ExecutionError("Failed due to KeyError while removing {}".format(args.env_name))

  @staticmethod
  def list(args):
    """
      Implements a command line method to list all environments that
      have been instantiated using `init`.
    """
    envs = EnvironmentManager.get_envs()
    if len(envs) == 0:
      display("(none)", color="red", stderr=False)
    else:
      for env in envs:
        EnvironmentManagerFactory(env_name=env, cmd='info').display_basic_info()

  @staticmethod
  def inventory(args):
    pretty_print(EnvironmentManagerFactory(env_name=args.env_name, cmd='info').inventory())

  @staticmethod
  def resources(args):
    """
      Implements command line method to provide more details on the AWS/CFT
      resources associated with a particular deployment.
      This includes vpc, subnets, bigip, app hosts, etc...
    """
    resources, statuses = EnvironmentManagerFactory(env_name=args.env_name, cmd='info').resources()
    for r in resources:
      print r
      pretty_print(statuses[r])
      
  @staticmethod
  def login(args):
    pretty_print(EnvironmentManagerFactory(env_name=args.env_name, cmd='info').login_info())

  @staticmethod
  def start_traffic(args):
    """
      Implements command line method to pass traffic through BIG-IP
    """
    exec_results = EnvironmentManagerFactory(env_name=args.env_name, cmd='info').start_traffic()
    print_playbook_results(exec_results)

  @staticmethod
  def stop_traffic(args):
    """
      Implements command line method to stop traffic through BIG-IP
    """
    exec_results = EnvironmentManagerFactory(env_name=args.env_name, cmd='info').stop_traffic()
    print_playbook_results(exec_results)