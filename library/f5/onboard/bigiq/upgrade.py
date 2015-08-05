#!/usr/bin/env python
"""Upgrade BIG-IQ VE on OpenStack."""
import sys
import os.path

top_dir = os.path.join(os.path.dirname(__file__), '../../..')
top_dir = os.path.abspath(top_dir)
sys.path.insert(0, top_dir)
from f5.common.util import get_cmd_output
ODK_DIR = get_cmd_output(
    ['bash', '-c', 'source odk-utils;echo $ODK_DIR'])[0]
sys.path.insert(0, ODK_DIR+'/python')

import argparse
import datetime
import time
from odk.setup.common.args import ADMIN_CREDS_PARSER
from odk.setup.common.args import BASE_PARSER
from odk.setup.common.args import CRUD_PARSER
from odk.setup.common.args import set_base_globals
from odk.setup.common.args import set_crud_globals
from odk.setup.common.util import get_ext_network_def
from odk.lib.openstack import OpenStackCreds
from odk.lib.nova import NovaLib
from odk.lib.neutron import NeutronFloatingIpLib
from odk.lib.neutron import NeutronNetworkLib

from f5.onboard.bigip.lib.check_state import BigIpCheckState

from f5.bigip import bigip as bigip_icontrol


def mylog(msg):
    """Logger"""
    print "%s: %s" % (datetime.datetime.now().strftime('%b %d %H:%M:%S'), msg)


class BigIqUpgrade(object):
    """BigIq Upgrade"""
    def __init__(self, admin_creds):
        self.nova_admin = NovaLib(admin_creds)
        self.netlib_admin = NeutronNetworkLib(admin_creds)
        floatlib_admin = NeutronFloatingIpLib(admin_creds)

        # get bigiq networks
        ext_network_def = get_ext_network_def(network_index=1)
        self.ext_net = self.netlib_admin.get_network(
            ext_network_def['network_name'])

        self.icontrol_hostnames = []
        self.icontrol_bigiqs = []

        for bigiq_index in range(0, ARGS.num_bigiqs):
            # get bigiq icontrol access address
            big = self.nova_admin.get_instance('bigiq' + str(bigiq_index+1))

            mgmt_port = self.netlib_admin.get_instance_port(big, 'bigiq_mgmt')
            floating_ip_addr = floatlib_admin.associate_port_floating_ip(
                self.ext_net, mgmt_port['id'])
            # configure icontrol to access bigiq
            self.icontrol_hostnames.append(floating_ip_addr)

        # connect
        self.__bigiqs = {}
        self.connected = False

    def set_up(self):
        """Set up environment"""
        # Wait for all devices to be active before starting the upgrade
        self.check_device_state(['active'])

        self._init_connections()
        all_devices = []
        for bigiq_index in range(0, ARGS.num_bigiqs):
            name = 'bigiq' + str(bigiq_index+1) + '.bigiqmgmt'
            all_devices.append(name)

        for bigiq_index in range(ARGS.num_bigiqs):
            ibig = self.icontrol_bigiqs[bigiq_index]

            mylog('Upgrading bigiq' + str(bigiq_index+1) + '.bigiqmgmt')
            ibig.system.sys_swmgmt.install_software_image_v2(
                "HD1.2",
                "BIG-IQ",
                ARGS.base_version,
                ARGS.hotfix_build,
                False, True, False)

        # Wait for install to complete
        hotfix = {}
        hotfix['install_volume'] = 'HD1.2'
        hotfix['base_version'] = ARGS.base_version
        hotfix['base_build'] = ARGS.base_build
        hotfix['hotfix_build'] = ARGS.hotfix_build
        self.check_hotfix_install_state(hotfix)

        # Wait for all devices to be active before proceeding
        self.check_device_state(['active'])
        mylog("Sleeping 5 minutes in an attempt to avoid exceptions")
        mylog("while clustering.")
        time.sleep(300)

    def tear_down(self):
        """Tear down environment"""
        pass

    def _init_connections(self):
        """Initialize bigiq connections"""
        if not self.connected:
            icontrol_creds = {'username': 'admin',
                              'password': 'admin'}

            for bigiq_index in range(0, ARGS.num_bigiqs):
                if not hasattr(self.__bigiqs,
                               self.icontrol_hostnames[bigiq_index]):
                    bigiq_to_add = bigip_icontrol.BigIP(
                        self.icontrol_hostnames[bigiq_index],
                        icontrol_creds['username'],
                        icontrol_creds['password'],
                        timeout=5,
                        address_isolation=True)
                    ic_hostname = self.icontrol_hostnames[bigiq_index]
                    self.__bigiqs[ic_hostname] = bigiq_to_add
                    self.icontrol_bigiqs.append(bigiq_to_add)
                    mylog('Connected to ' +
                          self.icontrol_hostnames[bigiq_index])
            self.connected = True

    def check_device_state(self, failover_states):
        """Helper to check device state"""
        bigiq_configs = []
        for bigiq_index in range(0, ARGS.num_bigiqs):
            bigiq_config = {}
            bigiq_config['name'] = 'bigiq%d' % (bigiq_index+1)
            bigiq_config['floating_ip_addr'] = \
                self.icontrol_hostnames[bigiq_index]
            bigiq_configs.append(bigiq_config)

        check_state = BigIpCheckState(bigiq_configs, product_name="BIG-IQ")
        check_state.check_device_state(failover_states)

    def check_hotfix_install_state(self, hotfix):
        """Helper to check hotfix state"""
        bigiq_configs = []
        for bigiq_index in range(0, ARGS.num_bigiqs):
            bigiq_config = {}
            bigiq_config['name'] = 'bigiq%d' % (bigiq_index+1)
            bigiq_config['floating_ip_addr'] = \
                self.icontrol_hostnames[bigiq_index]
            bigiq_configs.append(bigiq_config)

        check_state = BigIpCheckState(bigiq_configs, product_name="BIG-IQ")
        check_state.check_hotfix_install_state(hotfix)

if __name__ == '__main__':
    # pylint: disable=broad-except
    # Okay to catch Exception at top level
    try:
        PARSER = argparse.ArgumentParser(parents=[ADMIN_CREDS_PARSER,
                                                  BASE_PARSER,
                                                  CRUD_PARSER])
        PARSER.add_argument('--num-bigiqs',
                            type=int,
                            default=1,
                            help='Number of bigiqs to cluster')
        PARSER.add_argument('--base-version',
                            default=None,
                            help='Base version i.e. 11.5.0',
                            required=True)
        PARSER.add_argument('--base-build',
                            default=None,
                            help='Base Build i.e. 0.49.221',
                            required=True)
        PARSER.add_argument('--hotfix-build',
                            default=None,
                            help='Hotfix Build i.e. 0.49.221',
                            required=True)

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

        BIGIQ_UPGRADE = BigIqUpgrade(CREDS)
        if not ARGS.clean_up_only:
            BIGIQ_UPGRADE.set_up()
        if not ARGS.no_clean_up:
            BIGIQ_UPGRADE.tear_down()
    except Exception, exception:
        mylog('Exception: %s' % str(exception))
        exit(1)
    exit(0)
    # pylint: enable=broad-except
