#!/usr/bin/env python
"""Cluster BIG-IQs on OpenStack."""
import sys
import os.path

top_dir = os.path.join(os.path.dirname(__file__), '../../..')
top_dir = os.path.abspath(top_dir)
sys.path.insert(0, top_dir)
from f5.common.util import get_cmd_output
ODK_DIR = get_cmd_output(
    ['bash', '-c', 'source odk-utils;echo $ODK_DIR'])[0]
sys.path.insert(0, ODK_DIR+'/python')

F5_ONBOARD_DIR = get_cmd_output(
    ['bash', '-c', 'source f5-onboard-utils;echo $F5_ONBOARD_DIR'])[0]
sys.path.insert(0, F5_ONBOARD_DIR+'/python')

import argparse
import datetime

from odk.setup.common.args import ADMIN_CREDS_PARSER
from odk.setup.common.args import BASE_PARSER
from odk.setup.common.args import CRUD_PARSER
from odk.setup.common.args import set_base_globals
from odk.setup.common.args import set_crud_globals
from odk.setup.common.util import get_ext_network_def
from odk.lib.nova import NovaLib
from odk.lib.openstack import OpenStackCreds
from odk.lib.neutron import NeutronFloatingIpLib
from odk.lib.neutron import NeutronNetworkLib

from f5.onboard.bigiq.cluster_generic import BigIqClusterGeneric


def mylog(msg):
    """Logger"""
    print '%s: %s' % (datetime.datetime.now().strftime('%b %d %H:%M:%S'), msg)


# Given openstack creds, get all bigiqs' information and initiate clustering
class BigIqClusterVEonOS(object):
    """BigIq Cluster on OpenStack"""
    def __init__(self, admin_creds):
        nova_admin = NovaLib(admin_creds)
        self.netlib_admin = NeutronNetworkLib(admin_creds)
        self.floatlib_admin = NeutronFloatingIpLib(admin_creds)

        ext_network_def = get_ext_network_def(network_index=1)
        ext_net = self.netlib_admin.get_network(
            ext_network_def['network_name'])

        bigiq_configs = []
        for bigiq_index in range(0, ARGS.num_bigiqs):
            bigiq_config = {}
            bigiq_config['name'] = 'bigiq%d' % (bigiq_index+1)

            # get NAT to bigiq mgmt address
            big = nova_admin.get_instance('bigiq' + str(bigiq_index+1))
            mgmt_port = self.netlib_admin.wait_instance_port(big, 'bigiq_mgmt')
            bigiq_config['floating_ip_addr'] = \
                self.floatlib_admin.associate_port_floating_ip(ext_net,
                                                               mgmt_port['id'])

            # get the bigiq addresses used for clustering
            bigiq_config['mgmt_addr'] = \
                self.get_instance_network_addr(big, 'bigiq_mgmt')

            mylog('%s: floating_ip_addr %s, mgmt_addr %s' %
                  (bigiq_config['name'], bigiq_config['floating_ip_addr'],
                   bigiq_config['mgmt_addr']))

            bigiq_configs.append(bigiq_config)

        # cluster bigiqs using args and addresses
        self.cluster_generic = BigIqClusterGeneric(ARGS.bigiq_image,
                                                   ARGS.ha_type,
                                                   ARGS.num_bigiqs,
                                                   bigiq_configs)

    def set_up(self):
        """Set up environment"""
        self.cluster_generic.set_up()

    def tear_down(self):
        """Tear down environment"""
        pass

    def get_instance_network_addr(self, big, network):
        """Get addr for bigiq instance on a network.  Confirm only one addr."""
        net_port = self.netlib_admin.get_instance_port(big, network)
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
                                                  CRUD_PARSER])
        PARSER.add_argument('--bigiq-image',
                            help='Image of BIG-IQ to use.')
        PARSER.add_argument('--ha-type',
                            default='standalone',
                            help='standalone, pair, or scalen')
        PARSER.add_argument('--num-bigiqs',
                            type=int,
                            default=1,
                            help='Number of bigiqs to cluster')
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

        BIGIQ_CLUSTER_VE_ON_OS = BigIqClusterVEonOS(CREDS)
        if not ARGS.clean_up_only:
            BIGIQ_CLUSTER_VE_ON_OS.set_up()
        if not ARGS.no_clean_up:
            BIGIQ_CLUSTER_VE_ON_OS.tear_down()
    except Exception, exception:
        mylog('Exception: %s' % str(exception))
        import traceback
        traceback.print_exc()
        exit(1)
    exit(0)
    # pylint: enable=broad-except
