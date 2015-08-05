#!/usr/bin/env python
"""Cluster BIG-IPs on OpenStack."""
import sys
import os.path
import subprocess


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
ODK_DIR = get_cmd_output(
    ['bash', '-c', 'source odk-utils;echo $ODK_DIR'])[0]
sys.path.insert(0, ODK_DIR+'/python')

F5_ONBOARD_DIR = get_cmd_output(
    ['bash', '-c', 'source f5-onboard-utils;echo $F5_ONBOARD_DIR'])[0]
sys.path.insert(0, F5_ONBOARD_DIR+'/python')

import argparse
import datetime

from odk.setup.common.args import ADMIN_CREDS_PARSER
from odk.setup.common.args import TENANT_CREDS_PARSER
from odk.setup.common.args import BASE_PARSER
from odk.setup.common.args import CRUD_PARSER
from odk.setup.common.args import set_base_globals
from odk.setup.common.args import set_crud_globals
from odk.setup.common.util import get_creds
from odk.setup.common.util import get_ext_network_def
from odk.setup.common.util import get_network_def
from odk.lib.nova import NovaLib
from odk.lib.neutron import NeutronFloatingIpLib
from odk.lib.neutron import NeutronNetworkLib

from f5.onboard.bigip.cluster_generic import BigIpClusterGeneric


def mylog(msg):
    """Logger"""
    print '%s: %s' % (datetime.datetime.now().strftime('%b %d %H:%M:%S'), msg)


# Given openstack creds, get all bigips' information and initiate clustering
class BigIpClusterVEonOS(object):
    """BigIp Cluster on OpenStack"""
    def __init__(self, creds):
        self.nova_tenant = NovaLib(creds['admin'], creds['tenant'])

        self.neutron_network_admin = NeutronNetworkLib(
            creds['admin'], None)
        self.neutron_network_tenant = NeutronNetworkLib(
            creds['admin'], creds['tenant'])
        self.neutron_floating_ip_tenant = NeutronFloatingIpLib(
            creds['admin'], creds['tenant'])

        self.bigip_net_def = {}
        network_index = 10
        self.logical_net_names = ['mgmt', 'external', 'internal']
        if ARGS.ha_type != 'standalone':
            self.logical_net_names.extend(['ha', 'mirror'])
        for name in self.logical_net_names:
            self.bigip_net_def[name] = get_network_def(
                creds['tenant'].tenant_name, network_index=network_index)
            if name == 'external' and ARGS.external_network_name:
                self.bigip_net_def[name]['network_name'] =  \
                    ARGS.external_network_name
            elif name == 'internal' and ARGS.internal_network_name:
                self.bigip_net_def[name]['network_name'] = \
                    ARGS.internal_network_name
            else:
                self.bigip_net_def[name]['network_name'] = 'bigip_%s' % name
                network_index += 1

        ext_network_def = get_ext_network_def(network_index=1)
        ext_net = self.neutron_network_admin.get_network(
            ext_network_def['network_name'])

        bigip_configs = []
        for bigip_index in range(0, ARGS.num_bigips):
            bigip_config = {}
            bigip_config['name'] = 'bigip%d' % (bigip_index+1)

            # get NAT to bigip mgmt address
            big = self.nova_tenant.get_instance('bigip' + str(bigip_index+1))
            port = self.neutron_network_tenant.wait_instance_port(
                big, 'bigip_mgmt')
            bigip_config['floating_ip_addr'] = \
                self.neutron_floating_ip_tenant.associate_port_floating_ip(
                    ext_net, port['id'])

            # get the bigip addresses used for clustering
            bigip_config['mgmt_addr'] = \
                self.get_instance_network_addr(big, 'bigip_mgmt')

            if ARGS.ha_type != 'standalone':
                bigip_config['ha_addr'] = \
                    self.get_instance_network_addr(big, 'bigip_ha')

                bigip_config['mirror_addr'] = \
                    self.get_instance_network_addr(big, 'bigip_mirror')

                mylog('BIG-IP%d floating_ip_addr %s, mgmt_addr %s, '
                      'ha_addr %s, mirror_addr %s' %
                      (bigip_index+1, bigip_config['floating_ip_addr'],
                       bigip_config['mgmt_addr'], bigip_config['ha_addr'],
                       bigip_config['mirror_addr']))
            else:
                mylog('BIG-IP%d floating_ip_addr %s, mgmt_addr %s' %
                      (bigip_index+1, bigip_config['floating_ip_addr'],
                       bigip_config['mgmt_addr']))

            bigip_configs.append(bigip_config)

        # cluster bigips using args and addresses
        self.cluster_generic = BigIpClusterGeneric(
            ARGS.bigip_image, ARGS.ha_type, ARGS.num_bigips, bigip_configs)

    def set_up(self):
        """Set up environment"""
        self.cluster_generic.set_up()

    def tear_down(self):
        """Tear down environment"""
        pass

    def get_instance_network_addr(self, big, network):
        """Get addr for bigip instance on a network.  Confirm only one addr."""
        net_port = self.neutron_network_tenant.get_instance_port(big, network)
        num_ips = len(net_port['fixed_ips'])
        if num_ips != 1:
            mylog('ERROR: num fixed ips on port on %s network is %d but '
                  'should be 1' % (network, num_ips))
            exit(1)
        address = net_port['fixed_ips'][0]['ip_address']
        return address


if __name__ == '__main__':
    # pylint: disable=broad-except
    # Okay to catch Exception at top level
    try:
        PARSER = argparse.ArgumentParser(parents=[ADMIN_CREDS_PARSER,
                                                  BASE_PARSER,
                                                  CRUD_PARSER,
                                                  TENANT_CREDS_PARSER])
        PARSER.add_argument('--bigip-image',
                            metavar='bigip-image',
                            help='Image of BIG-IP to use.')
        PARSER.add_argument('--ha-type',
                            metavar='ha-type',
                            default='pair',
                            help='standalone, pair, or scalen')
        PARSER.add_argument('--num-bigips',
                            type=int,
                            metavar='number-of-bigips',
                            default=2,
                            help='Number of bigips to cluster')
        PARSER.add_argument('--external-network-name',
                            metavar='external-network-name',
                            help='Bigip external network name.')
        PARSER.add_argument('--internal-network-name',
                            metavar='internal-network-name',
                            help='Bigip internal network name.')
        ARGS = PARSER.parse_args()

        set_base_globals(
            openstack_api_endpoint=ARGS.openstack_api_endpoint,
            verbose=ARGS.verbose)

        set_crud_globals(
            check=ARGS.check,
            sleep=ARGS.sleep)

        CREDS = get_creds(ARGS)

        BIGIP_CLUSTER_VE_ON_OS = BigIpClusterVEonOS(CREDS)
        if not ARGS.clean_up_only:
            BIGIP_CLUSTER_VE_ON_OS.set_up()
        if not ARGS.no_clean_up:
            BIGIP_CLUSTER_VE_ON_OS.tear_down()
    except Exception, exception:
        mylog('Exception: %s' % str(exception))
        import traceback
        traceback.print_exc()
        exit(1)
    exit(0)
    # pylint: enable=broad-except
