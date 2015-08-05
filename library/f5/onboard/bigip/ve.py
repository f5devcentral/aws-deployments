#!/usr/bin/env python
"""Deploy BIG-IP VE on OpenStack."""
import sys
import os.path
import subprocess
import json


def get_cmd_output(cmd_array):
    """Get output from command"""
    proc = subprocess.Popen(cmd_array, stdout=subprocess.PIPE)
    retval = []
    for line in iter(proc.stdout.readline, ''):
        retval.append(line.rstrip())
    return retval

top_dir = os.path.join(os.path.dirname(__file__), '../../..')
top_dir = os.path.abspath(top_dir)
sys.path.insert(0, top_dir)
HOMEDIR = os.path.expanduser("~")

ODK_DIR = get_cmd_output(['bash', '-c', 'source odk-utils;echo $ODK_DIR'])[0]
sys.path.insert(0, ODK_DIR + '/python')

import argparse
from odk.setup.common.args import ADMIN_CREDS_PARSER
from odk.setup.common.args import BASE_PARSER
from odk.setup.common.args import CRUD_PARSER
from odk.setup.common.args import set_base_globals
from odk.setup.common.args import set_crud_globals
from odk.setup.common.util import get_ext_network_def
from odk.setup.common.util import get_network_def
from odk.setup.common.util import PORT_SSH
from odk.lib.connect import test_connectivity
from odk.lib.nova import NovaLib
from odk.lib.openstack import OpenStackCreds
from odk.lib.neutron import NeutronFloatingIpLib
from odk.lib.neutron import NeutronNetworkLib

BIG_IP_FLAVOR = {'name': 'm1.bigip',
                 'ram': 4096,
                 'vcpus': 2,
                 'disk': 120}


class BigipVE(object):
    """Bigip VE"""
    def __init__(self, admin_creds, args):
        self.args = args
        self.nova_admin = NovaLib(admin_creds)
        # validate image exists
        image = self.nova_admin.get_image(name=args.bigip_image)
        if not image:
            raise ValueError('Nova image %s does not exist' % args.bigip_image)
        # glean integration data from image metadata
        flavor_confirmed = False
        self.instance_meta = {}
        # use flavor specified in image if tagged by metadata
        if 'nova_flavor' in image.metadata:
            flavor_name = image.metadata['nova_flavor']
            flavor = self.nova_admin.get_flavor(flavor_name)
            if flavor:
                flavor_confirmed = True
                BIG_IP_FLAVOR['name'] = flavor.name
                BIG_IP_FLAVOR['ram'] = flavor.ram
                BIG_IP_FLAVOR['vcpus'] = flavor.vcpus
                BIG_IP_FLAVOR['disk'] = flavor.disk
        # copy known metadata from image to instance
        for md in image.metadata:
            if str(md).startswith('os_'):
                self.instance_meta[md] = image.metadata[md]
        # did not discover from flavor metadata
        if not flavor_confirmed:
            # was an image explicitly defined by ARGS.bigip_flavor
            if args.bigip_flavor:
                flavor = self.nova_admin.get_flavor(args.bigip_flavor)
                if flavor:
                    flavor_confirmed = True
                    BIG_IP_FLAVOR['name'] = flavor.name
                    BIG_IP_FLAVOR['ram'] = flavor.ram
                    BIG_IP_FLAVOR['vcpus'] = flavor.vcpus
                    BIG_IP_FLAVOR['disk'] = flavor.disk
            else:
                # See if the default flavor exists, if not create it
                flavor = self.nova_admin.get_flavor(BIG_IP_FLAVOR['name'])
                if not flavor:
                    flavor = self.nova_admin.create_flavor(
                        BIG_IP_FLAVOR['name'],
                        BIG_IP_FLAVOR['ram'],
                        BIG_IP_FLAVOR['vcpus'],
                        BIG_IP_FLAVOR['disk']
                    )
        # setup neutron network and floating IP admin clients
        self.neutron_floating_ip_admin = NeutronFloatingIpLib(admin_creds)
        self.neutron_network_admin = NeutronNetworkLib(admin_creds)
        # define external network for floating IPs
        if not self.args.no_floating_ips:
            ext_network_def = get_ext_network_def(network_index=1)
            self.ext_net = self.neutron_network_admin.get_network(
                ext_network_def['network_name'])
            if not self.ext_net:
                exnets = self.neutron_network_admin.get_external_networks()
                if len(exnets) < 1:
                    raise Exception("Cannot get network: network_name: %s" %
                                    ext_network_def['network_name'])
                else:
                    self.ext_net = exnets[0]
        # build network definitions
        self.bigip_net_def = {}
        self.logical_net_names = []
        network_index = 1
        # neutron network lookup cache
        self.networks_by_name = {}
        # user the user explicitly defined networks
        if args.bigip_mgmt_network or args.bigip_networks:
            nc = self.neutron_network_admin
            if args.bigip_mgmt_network:
                network = nc.get_network(args.bigip_mgmt_network)
                if network:
                    self.networks_by_name['mgmt'] = network
                    self.bigip_net_def['mgmt'] = {
                        'network_name': network['name']
                    }
                    self.logical_net_names.append('mgmt')
                else:
                    self.logical_net_names.append('mgmt')
                    self.bigip_net_def['mgmt'] = get_network_def(
                        admin_creds.tenant_name,
                        network_index=network_index
                    )
                    self.bigip_net_def['mgmt']['network_name'] = 'bigip_mgmt'
            if args.bigip_networks:
                for network_name in args.bigip_networks:
                    network = nc.get_network(network_name)
                    if network:
                        self.networks_by_name[network['name']] = network
                        self.bigip_net_def[network['name']] = {
                            'network_name': network['name']
                        }
                        self.logical_net_names.append(network['name'])
        else:
            # use default network definitions for the test framework
            ext_network_def = get_ext_network_def(network_index=1)
            self.ext_net = self.neutron_network_admin.get_network(
                ext_network_def['network_name'])
            self.logical_net_names = ['mgmt',
                                      'external',
                                      'internal',
                                      'datanet']
            if args.ha_type != 'standalone':
                self.logical_net_names.extend(['ha', 'mirror'])
            for name in self.logical_net_names:
                if name == 'datanet':
                    continue
                self.bigip_net_def[name] = get_network_def(
                    admin_creds.tenant_name, network_index=network_index)
                network_index += 1
                self.bigip_net_def[name]['network_name'] = 'bigip_%s' % name

    def build_instance_nic_list(self):
        """Create nics array"""
        nics = []
        for logical_net_name in self.logical_net_names:
            if logical_net_name == 'datanet':
                net_name = 'datanet'
            else:
                net_name = self.bigip_net_def[logical_net_name]['network_name']
            if net_name in self.networks_by_name:
                net = self.networks_by_name[net_name]
            else:
                net = self.neutron_network_admin.get_network(net_name)
            nics.append({'net-id': net['id']})
        return nics

    def set_up(self, floating_ip_retry=60):
        """Set up environment"""

        nics = self.build_instance_nic_list()
        instances = []
        userdatas = {}
        if self.args.bigip_userdata:
            bigip_index = int(self.args.bigip_index)
            for data_file in self.args.bigip_userdata:
                if os.path.isfile(data_file):
                    ud_fd = open(data_file)
                    userdatas[bigip_index] = ud_fd.read()
                    ud_fd.close()
                else:
                    try:
                        json.loads(data_file)
                        userdatas[bigip_index] = data_file
                    except:
                        pass
                bigip_index += 1

        for bigip_index in range(int(self.args.bigip_index),
                                 int(self.args.bigip_index) +
                                 int(self.args.num_bigips)):
            instance_name = '%s%d' % (self.args.bigip_name, bigip_index)
            server = self.nova_admin.get_instance(instance_name)
            if not server:
                userdata = None
                if bigip_index in userdatas:
                    userdata = userdatas[bigip_index]
                else:
                    fn = '%s/.f5-onboard/tmp/startup_metadata_%d.json' % \
                        (HOMEDIR, bigip_index)
                    if os.path.isfile(fn):
                        userdata_file = open(fn)
                        userdata = userdata_file.read()
                        userdata_file.close()
                security_group = 'default'
                if self.args.security_group:
                    security_group = self.args.security_group
                if self.args.key_name:
                    key_name = self.args.key_name
                meta = []
                if self.args.meta:
                    meta = self.args.meta
                instances.append(self.nova_admin.create_instance(
                    name=instance_name, image_name=self.args.bigip_image,
                    flavor_name=BIG_IP_FLAVOR['name'],
                    security_groups=[security_group], key_name=key_name,
                    nics=nics, userdata=userdata, meta=meta))

            if not self.args.no_floating_ips:
                floating_ip_addrs = ''
                for instance in instances:
                    # Create floating ip and test connectivity
                    bigip_mgmt_name = \
                        self.bigip_net_def['mgmt']['network_name']
                    port = self.neutron_network_admin.wait_instance_port(
                        instance, bigip_mgmt_name)
                    floating_ip_addr = self.neutron_floating_ip_admin.\
                        associate_port_floating_ip(self.ext_net, port['id'])
                    if not test_connectivity(floating_ip_addr, PORT_SSH,
                                             floating_ip_retry):
                        raise Exception('Instance connectivity test failed.')
                    if floating_ip_addrs:
                        floating_ip_addrs += (',' + floating_ip_addr)
                    else:
                        floating_ip_addrs = floating_ip_addr
                if not self.args.no_floating_ips_file:
                    statefile = open(
                        ('%s/.f5-onboard/tmp/bigip-addrs' % HOMEDIR), 'w')
                    statefile.write(floating_ip_addrs)
                    statefile.close()

    def tear_down(self):
        """Tear down environment"""
        bigip_mgmt_name = self.bigip_net_def['mgmt']['network_name']
        for bigip_index in range(int(self.args.bigip_index),
                                 int(self.args.bigip_index) +
                                 int(self.args.num_bigips)):
            instance_name = '%s%d' % (self.args.bigip_name, bigip_index)
            instance = self.nova_admin.get_instance(instance_name)
            if instance:
                port = self.neutron_network_admin.get_instance_port(
                    instance, bigip_mgmt_name)
                if port:
                    floating_ip_addr = self.neutron_floating_ip_admin.\
                        get_port_floating_ip_addr(port['id'])
                    if floating_ip_addr:
                        self.neutron_floating_ip_admin.delete_floating_ip(
                            floating_ip_addr)

                self.nova_admin.delete_instance(instance)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    # pylint: disable=broad-except
    # Okay to catch Exception at top level
    try:
        PARSER = argparse.ArgumentParser(parents=[ADMIN_CREDS_PARSER,
                                                  BASE_PARSER,
                                                  CRUD_PARSER])
        PARSER.add_argument('--bigip-image',
                            metavar='bigip-image',
                            help='Image of BIG-IP to use.')
        PARSER.add_argument('--bigip-index',
                            metavar='bigip-index',
                            default='1',
                            help='Starting index of  BIG-IP to act on. \
                                  The first is 1.')
        PARSER.add_argument('--num-bigips',
                            metavar='num-bigips',
                            default='1',
                            help='How many BIG-IPs to launch.')
        PARSER.add_argument('--ha-type',
                            metavar='ha-type',
                            default='pair',
                            help='HA type: standalone, pair, or scalen.')
        PARSER.add_argument('--mgmt-ips-file',
                            metavar='mgmt-ips-file',
                            help='File to write floating-ips assigned to \
                                  the big-ips.')

        # Added implicitly defined attributes
        PARSER.add_argument(
            '--bigip-name',
            metavar='bigip-name',
            default='bigip',
            help='Prefix to use for BIG-IP name, postfixed by the index.'
        )
        PARSER.add_argument(
            '--bigip-flavor',
            metavar='bigip-flavor',
            default=None,
            help='Flavor name or ID to use for the BIG-IP.'
        )
        PARSER.add_argument(
            '--security-group',
            metavar='security-group',
            default=None,
            help='Security Group name to use for the BIG-IP.'
        )
        PARSER.add_argument(
            '--key-name',
            metavar='key-name',
            default=None,
            help='SSH key to use for the BIG-IP.'
        )
        PARSER.add_argument(
            '--meta',
            metavar='meta',
            nargs='*',
            help='Metadata to tag the VE'
        )
        PARSER.add_argument(
            '--no-floating-ips',
            action='store_true',
            metavar='no-floating-ips',
            default=False,
            help='Disable floating-ip creation for mgmt addresses.'
        )
        PARSER.add_argument(
            '--no-floating-ips-file',
            action='store_true',
            metavar='no-floating-ips-file',
            default=False,
            help='Disable floating-ip creation for mgmt addresses.'
        )
        PARSER.add_argument(
            '--bigip-mgmt-network',
            metavar='bigip-mgmt-network',
            default=None,
            help='The name name or ID for management access.'
        )
        PARSER.add_argument(
            '--bigip-networks',
            metavar='bigip-networks',
            nargs='*',
            help='List of network names or IDs for the VE'
        )
        PARSER.add_argument(
            '--bigip-userdata',
            metavar='bigip-userdata',
            nargs='*',
            help='Ordered list of userdata for the VEs'
        )
        ARGS = PARSER.parse_args()

        set_base_globals(
            openstack_api_endpoint=ARGS.openstack_api_endpoint,
            verbose=ARGS.verbose)

        set_crud_globals(
            check=ARGS.check,
            sleep=ARGS.sleep)

        CREDS = OpenStackCreds(ARGS.admin_tenant_name,
                               ARGS.admin_username,
                               ARGS.admin_password)

        BIGIP_VE = BigipVE(CREDS, ARGS)
        if not ARGS.clean_up_only:
            BIGIP_VE.set_up()
        if not ARGS.no_clean_up:
            BIGIP_VE.tear_down()
    except Exception, exception:
        import traceback
        traceback.print_exc()
        exit(1)
    exit(0)
    # pylint: enable=broad-except


if __name__ == "__main__":
    sys.exit(main())
