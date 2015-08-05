#!/usr/bin/env python
"""Deploy BIG-IP VE on OpenStack."""
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

import argparse
import datetime
import time
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

from f5.onboard.bigip.lib.check_state import BigIpCheckState

from f5.bigip import bigip as bigip_icontrol


def mylog(msg):
    """Logger"""
    print "%s: %s" % (datetime.datetime.now().strftime('%b %d %H:%M:%S'), msg)


class BigIpUpgrade(object):
    """BigIp Upgrade"""
    def __init__(self, creds):
        nova_tenant = NovaLib(creds['admin'], creds['tenant'])

        neutron_network_admin = NeutronNetworkLib(
            creds['admin'], None)
        neutron_network_tenant = NeutronNetworkLib(
            creds['admin'], creds['tenant'])
        neutron_floating_ip_tenant = NeutronFloatingIpLib(
            creds['admin'], creds['tenant'])

        # get bigip networks
        self.bigip_net_def = {}
        network_index = 10
        logical_net_names = ['mgmt', 'external', 'internal']
        for name in logical_net_names:
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
        self.ext_net = neutron_network_admin.get_network(
            ext_network_def['network_name'])

        self.icontrol_hostnames = []
        self.icontrol_bigips = []
        for bigip_index in range(0, ARGS.num_bigips):
            # get bigip icontrol access address
            big = nova_tenant.get_instance('bigip' + str(bigip_index+1))

            port = neutron_network_tenant.get_instance_port(
                big, self.bigip_net_def['mgmt']['network_name'])
            floating_ip_addr = \
                neutron_floating_ip_tenant.associate_port_floating_ip(
                    self.ext_net, port['id'])
            # configure icontrol to access bigip
            self.icontrol_hostnames.append(floating_ip_addr)
            #mylog("BIG-IP at " + floating_ip_addr)

        # connect
        self.__bigips = {}
        self.connected = False

    def set_up(self):
        """Set up environment"""
        # Wait for all devices to be active before starting the upgrade
        self.check_device_state(['active'])

        self._init_connections()
        all_devices = []
        for bigip_index in range(0, ARGS.num_bigips):
            name = 'bigip' + str(bigip_index+1) + '.bigipmgmt'
            all_devices.append(name)

        for bigip_index in range(ARGS.num_bigips):
            ibig = self.icontrol_bigips[bigip_index]

            mylog('Upgrading bigip' + str(bigip_index+1) + '.bigipmgmt')
            ibig.system.sys_swmgmt.install_software_image_v2(
                "HD1.2",
                "BIG-IP",
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
        """Initialize bigip connections"""
        if not self.connected:
            icontrol_creds = {'username': 'admin',
                              'password': 'admin'}

            for bigip_index in range(0, ARGS.num_bigips):
                #self.__last_connect_attempt = datetime.datetime.now()

                if not hasattr(self.__bigips,
                               self.icontrol_hostnames[bigip_index]):
                    bigip_to_add = bigip_icontrol.BigIP(
                        self.icontrol_hostnames[bigip_index],
                        icontrol_creds['username'],
                        icontrol_creds['password'],
                        timeout=5,
                        address_isolation=True)
                    ic_hostname = self.icontrol_hostnames[bigip_index]
                    self.__bigips[ic_hostname] = bigip_to_add
                    self.icontrol_bigips.append(bigip_to_add)
                    #if bigip_index is 0:
                    #    self.first_bigip = bigip_to_add
                    mylog('Connected to ' +
                          self.icontrol_hostnames[bigip_index])
            self.connected = True

    def check_device_state(self, failover_states):
        """Helper to check device state"""
        bigip_configs = []
        for bigip_index in range(0, ARGS.num_bigips):
            bigip_config = {}
            bigip_config['name'] = 'bigip%d' % (bigip_index+1)
            bigip_config['floating_ip_addr'] = \
                self.icontrol_hostnames[bigip_index]
            bigip_configs.append(bigip_config)

        check_state = BigIpCheckState(bigip_configs)
        check_state.check_device_state(failover_states)

    def check_hotfix_install_state(self, hotfix):
        """Helper to check hotfix state"""
        bigip_configs = []
        for bigip_index in range(0, ARGS.num_bigips):
            bigip_config = {}
            bigip_config['name'] = 'bigip%d' % (bigip_index+1)
            bigip_config['floating_ip_addr'] = \
                self.icontrol_hostnames[bigip_index]
            bigip_configs.append(bigip_config)

        check_state = BigIpCheckState(bigip_configs)
        check_state.check_hotfix_install_state(hotfix)

if __name__ == '__main__':
    # pylint: disable=broad-except
    # Okay to catch Exception at top level
    try:
        PARSER = argparse.ArgumentParser(parents=[ADMIN_CREDS_PARSER,
                                                  BASE_PARSER,
                                                  CRUD_PARSER,
                                                  TENANT_CREDS_PARSER])
        PARSER.add_argument('--num-bigips',
                            type=int,
                            metavar='number-of-bigips',
                            default=2,
                            help='Number of bigips to cluster')
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

        BIGIP_UPGRADE = BigIpUpgrade(CREDS)
        if not ARGS.clean_up_only:
            BIGIP_UPGRADE.set_up()
        if not ARGS.no_clean_up:
            BIGIP_UPGRADE.tear_down()
    except Exception, exception:
        mylog('Exception: %s' % str(exception))
        exit(1)
    exit(0)
    # pylint: enable=broad-except
