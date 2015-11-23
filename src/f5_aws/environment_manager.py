import re
import os
import json
import yaml

import ansible.utils

from f5_aws.config import Config
from f5_aws.utils import convert_str
from f5_aws.playbook_runner import PlaybookRunner, display
from f5_aws.exceptions import ExecutionError, ValidationError, LifecycleError

# make our config global
config = Config().config


def EnvironmentManagerFactory(env_name="", cmd="", extra_vars=""):
    """
      This method is an entry point for instantiations of this class 
      which do not occur through the command line (i.e. tests, and
        the worker processes for our service catalog app)
    """
    from f5_aws import cli

    arg_list = []
    arg_list.append(cmd)
    if cmd == "info":
        # nasty stuff here because of http://bugs.python.org/issue9253
        #  optional subparsers are not allowed
        # we add one of the subparser commands to fit the argparse description
        arg_list.append("resources")

    if env_name:
        arg_list.append(env_name)
    if extra_vars:
        arg_list.append("--extra-vars")
        arg_list.append(json.dumps(extra_vars))

    parser = cli.get_parser()
    args = parser.parse_args(arg_list)

    return EnvironmentManager(args)


class EnvironmentManager(object):
    config = config

    @staticmethod
    def get_envs():
        """Gets a list of all deployments"""
        return os.listdir(config['env_path'])

    @staticmethod
    def host_to_az(resource_name, ansible_inventory):
        """Traverse the ansible inventory to get the availability zone"""
        # for this host
        try:
            hostname = resource_name
            az = ansible_inventory.get_host(
                hostname).get_variables()["availability_zone"]
            return "{}/{}".format(az, resource_name)
        except:
            return ""

    @staticmethod
    def get_matching_playbooks(playbooks, match_exprs):
        """
                Takes in a list of playbooks and returns a subset of these
                which match those in match_expr.  Return set includes only
                unique elements in originally order. 
        """
        matching_playbooks = []
        for pb in playbooks:
            for expr in match_exprs:
                if expr in pb:
                    matching_playbooks.append(pb)

        # remove the duplicates
        output = []
        seen = set()
        for pb in matching_playbooks:
            if pb not in seen:
                output.append(pb)
                seen.add(pb)
        return output


    def __init__(self, args):
        """
          When the playbooks are run, there are two sets of variables
          passed to ansible:

            #1
            options - This set of variables tells ansible 
            how to behave (e.g. self.options.forks in playbook_runner.py). 
            We use default values for most of these, stolen mostly from
            the out-of-the-box `ansible-playbook` executable.

            #2
            extra_vars - These are variables made available
            in the global scope during a play or task.
            Any variables passed to our command line using the --extra-vars
            parameter are passed are added to the extra_vars dict.

            In addition to variables passed on the command line by the user, 
            below we set additional variables in the global scope during 
            certain execution contexts. Note that many additional variables
            are set within playbook_runner.py

        """

        self.options = args
        self.extra_vars = {}

        for v in config["required_vars"]:
            self.extra_vars[v] = config[v]
        self.extra_vars["env_path"] = config["env_path"]

        # cloudformation templates will need just the key name, without any
        # extension
        self.extra_vars["ssh_key_name"] = config[
            "ssh_key"].split("/")[-1].split(".")[0]

        if getattr(self.options, "env_name", None):
            self.extra_vars["env_name"] = getattr(self.options, "env_name")

        for extra_vars_opt in getattr(self.options, "extra_vars", []):
            self.extra_vars = ansible.utils.combine_vars(self.extra_vars,
                                                         ansible.utils.parse_yaml(extra_vars_opt))

        # the first inventory just contains a local host to run the init
        # playbook
        self.proj_inventory_path = config["install_path"] + "/inventory/hosts"
        # the second inventory is specific to this deployment
        self.env_inventory_path = "%s/%s/inventory/hosts" % (
            config["env_path"], self.options.env_name)

    def init(self):
        """
        To instantiate a new environment, we create a set
        of inventory files for that environment. 

        See individual playbooks for more info. 
        """

        # basic string checking to prevent failures later in playbook
        if not re.match("^[a-zA-z]{1}[a-zA-Z0-9-]*", self.options.env_name):
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

        # TODO: validate images, eip and cloudformation limits, EULA
        # acceptance?

        playbooks = ["init.yml"]
        playbook_context = PlaybookRunner(
            playbooks, config, self.proj_inventory_path, self.options, self.extra_vars)
        playbook_context.run()

        return {"playbook_results": playbook_context, "env": self}

    def deploy(self):
        """
        Run ansible playbooks for deployment, given the ansible
        inventory created via 'init'
        """
        # make sure the environment has been initialized
        envs = EnvironmentManager.get_envs()
        if not self.options.env_name in envs:
            raise LifecycleError("Environment '{}' does not exist.  Has it been initialized?".format(
                self.options.env_name))

        playbooks = [
            'deploy_vpc_cft.yml',
            'deploy_az_cft.yml',
            'deploy_bigip_cft.yml',
            'deploy_gtm_cft.yml',
            'deploy_app_cft.yml',
            'deploy_client_cft.yml',
            'deploy_analytics_cft.yml',
            'deploy_app.yml',
            'deploy_bigip.yml',
            'cluster_bigips.yml',
            'deploy_apps_bigip.yml',
            'deploy_gtm.yml',
            'deploy_apps_gtm.yml',
            'deploy_client.yml',
            'deploy_analytics.yml'
        ]

        if self.extra_vars.get("run_only"):
            print 'User specified subset of playbooks to run specified by {}'.format(
                self.extra_vars["run_only"])
            matching_playbooks = self.get_matching_playbooks(
                playbooks, self.extra_vars["run_only"])
        else:
            matching_playbooks = playbooks

        print 'Running playbooks {}'.format(matching_playbooks)

        playbook_context = PlaybookRunner(
            matching_playbooks, config, self.env_inventory_path,
            self.options, self.extra_vars)
        playbook_context.run()

        return {"playbook_results": playbook_context, "env": self}

    def teardown(self):
        playbooks = ["teardown_all.yml"]

        playbook_context = PlaybookRunner(
            playbooks, config, self.env_inventory_path,
            self.options, self.extra_vars)
        playbook_context.run()

        return {"playbook_results": playbook_context, "env": self}

    def start_traffic(self):
        playbooks = ["start_traffic.yml"]

        playbook_context = PlaybookRunner(
            playbooks, config, self.env_inventory_path,
            self.options, self.extra_vars)
        playbook_context.run()

        return {"playbook_results": playbook_context, "env": self}

    def stop_traffic(self):
        playbooks = ["stop_traffic.yml"]

        playbook_context = PlaybookRunner(
            playbooks, config, self.env_inventory_path,
            self.options, self.extra_vars)
        playbook_context.run()

        return {"playbook_results": playbook_context, "env": self}

    def remove(self):
        inventory, resources, statuses = self.get_environment_info()

        okToRemove = True
        stillExists = []
        for r in resources:
            if statuses[r]["state"] == "deployed":
                okToRemove = False
                stillExists.append(r)

        if okToRemove is True:
            # uses the inventory included in this repository
            playbooks = ["remove.yml"]
            print "running {}".format(playbooks)
            inventory_path = config["install_path"] + "/inventory/hosts"
            playbook_context = PlaybookRunner(
                playbooks, config, inventory_path, self.options, self.extra_vars)
            playbook_context.run()
            return {"playbook_results": playbook_context, "env": self}
        else:
            raise LifecycleError("""Cannot remove environment '%s' until all resources have been de-provisioned.
The following resources still exist: %s\n
Hint: Try tearing down the environment first.""" % (
                self.options.env_name, stillExists))

    def inventory(self):
        inventory, resources, statuses = self.get_environment_info()
        return inventory

    def resources(self):
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
            'clienthost': 'ClientInstancePublicIp',
            'analyticshost': 'AnalyticsServerInstancePublicIp'
        }

        for host_type in ip_map.keys():
            try:
                group_name = host_type + "s"
                if inventory[group_name]:
                    group_info = inventory[group_name]
                    login_info[host_type] = {}

                    # not very efficient...
                    for resource_name, status in statuses.items():
                        match = re.match(
                            "^zone[0-9]+[/-]{}[0-9]+".format(host_type), resource_name)

                        if match:
                            try:
                                resources = {}
                                key = group_info["vars"][
                                    "ansible_ssh_private_key_file"]
                                user = group_info["vars"]["ansible_ssh_user"]
                                ip = status["resource_vars"][ip_map[host_type]]
                                resources["ssh"] = "ssh -i {} {}@{}".format(
                                    key, user, ip)

                                if "app" in resource_name:
                                    resources["http"] = "http://{}".format(ip)

                                if "bigip" in resource_name:
                                    resources["virtual_servers"] = self.collect_virtual_servers(
                                        resource_name)
                                    resources["elastic_ips"] = self.collect_elastic_ips(
                                        resource_name)
                                    resources["https"] = "https://{}".format(ip)
                                
                                if "gtm" in resource_name:
                                    resources["wideips"] = self.collect_wideips(
                                        resource_name)
                                    resources["elastic_ips"] = self.collect_elastic_ips(
                                        resource_name)
                                    resources["https"] = "https://{}".format(ip)
                                
                                if 'analyticshost' in resource_name:
                                    resources['http_username'] = 'admin'
                                    resources['http'] = 'http://{}:8000'.format(ip)

                                login_info[host_type][self.host_to_az(
                                    resource_name, ansible_inventory)] = resources
                            except KeyError, e:
                                pass
            except KeyError, e:
                pass

        return login_info

#################################################################
#### all over the below needs to get refactored....very ugly ####
#################################################################

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

        env_info = inventory['all']['vars']
    	del env_info['env_name']	
        display(" - %s (%s)" % (self.options.env_name, status),
                color=color, stderr=False)
        for k in sorted(env_info, key=lambda key: key):
            display("  %s: %s" %
                    (k, env_info[k]), color=color, stderr=False)

    def get_environment_info(self):

        # collect the ansible inventory in a nice format
        ansible_inventory = ansible.inventory.Inventory(
            self.env_inventory_path, vault_password=None)
        inventory = {}
        for group, hosts in ansible_inventory.groups_list().items():
            inventory[group] = {
                "hosts": hosts,
                "vars": ansible_inventory.get_group(group).vars
            }

        resources, statuses = self.get_latest_status(inventory)

        # clusters also show up in the statuses section, but we cannot
        #  print their status now, this causes them to show up under
        #  state = 'not deployed/error' for all models.  Avoiding this
        #  for now by removing them from the objects below
        for i, r in enumerate(resources):
            if 'cluster' in r:
                del statuses[r]
                del resources[i]

        return inventory, resources, statuses

    def collect_elastic_ips(self, resource_name):
        return self.collect_resources(resource_name, "{}-vip-Vip[0-9]+.json",
                                     ["eipAddress", "privateIpAddress"], False)

    def collect_virtual_servers(self, resource_name):
        return self.collect_resources(resource_name, "facts_{}.json",
                                     ["name", "destination"], True)
    def collect_wideips(self, resource_name):
        return self.collect_resources(resource_name, "facts_{}.json",
                                     ["name"], True)

    def collect_resources(self, resource_name, fregex, fields, nested):
        r = []
        try:
            searchDir = "%s/%s/" % (config["env_path"], self.options.env_name)
            files = os.listdir(searchDir)
            for fname in files:
                if re.match(fregex.format(resource_name), fname):
                    with open(searchDir + fname) as data_file:
                        content = json.load(data_file)
                        if nested == False:
                            r.append(
                                dict(zip(fields, [content[x] for x in fields])))
                        else:
                            for i in content["items"]:
                                r.append(
                                    dict(zip(fields, [i[x] for x in fields])))
        except KeyError, e:
            print "WARN: %s" % e
        return r

    def get_latest_status(self, inventory):
        """
          Attempts to read the output from executed tasks.
        """

        hosts = [h for h in inventory["all"]["hosts"]]
        statuses = {}
        resources = []
        for m in hosts:
            # for each resource, we will get the results from
            #  most recent manager execution for that resource
            #resource_name = m[:-8]
            resource_name = m[:]

            resources.append(resource_name)
            try:
                fname = "{}/{}/{}.yml".format(
                    config["env_path"], self.options.env_name, m)
                with open(fname) as f:
                    latest = yaml.load(f)
                    statuses[resource_name] = getattr(self,
                                                      "state_" +
                                                      latest["invocation"][
                                                          "module_name"])(latest, True)

            except Exception as e:
                statuses[resource_name] = {"state": "not deployed/error"}

        return resources, statuses

    def state_cloudformation(self, latest_result, show_resource_vars):
        """
          Parses the output from the ansible `cloudformation` module. We do
          this because there isn't an easy way to tell if a stack doesn't exist.
          https://github.com/ansible/ansible-modules-core/issues/1370#issuecomment-126083403
        """
        result = {}
        cf = convert_str(latest_result["invocation"]["module_args"])

        # we need to handle 'present' and 'absent' situations differently
        if cf["state"] == "present":
            result["stack_name"] = cf["stack_name"]
            if show_resource_vars:
                result["resource_vars"] = latest_result["stack_outputs"]
            if (latest_result["output"] == "Stack CREATE complete" or
                    latest_result["output"] == "Stack is already up-to-date."):
                result["state"] = "deployed"
            else:
                result["state"] = "deploy-error"
        else:  # state == "absent"...
            # We need to deal with the case where the stack does not exist
            # in a particular fashion for the command line `descibe` and
            # `list commands.
            if (latest_result.get("output", "") == "Stack Deleted" or
                    "does not exist" in latest_result.get("msg", "")):
                result["state"] = "absent"
            else:
                result["state"] = "teardown-error"

        return result
