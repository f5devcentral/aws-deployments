#!/usr/bin/env python
"""Cluster BIG-IQs on OpenStack."""
import sys
import os.path
top_dir = os.path.join(os.path.dirname(__file__), '../../../..')
top_dir = os.path.abspath(top_dir)
sys.path.insert(0, top_dir)

import argparse
import datetime

from time import sleep

from f5.bigip import bigip as bigip_icontrol
from f5.onboard.bigip.lib.check_state import BigIpCheckState


def mylog(msg):
    """Logger"""
    print '%s: %s' % (datetime.datetime.now().strftime('%b %d %H:%M:%S'), msg)


class BigIqClusterGeneric(object):
    """BigIq Generic Clustering"""
    def __init__(self, bigiq_image, ha_type, num_bigiqs, bigiq_configs):
        if ha_type != "standalone":
            raise Exception('Only ha_type standalone is currently supported.')

        self.cluster_args = {}
        self.cluster_args['bigiq_image'] = bigiq_image
        self.cluster_args['ha_type'] = ha_type
        self.cluster_args['num_bigiqs'] = num_bigiqs

        self.bigiq_configs = bigiq_configs
        self.icontrol_bigiqs = []
        self.connected = False
        self.connected_by_access_addr = {}
        self.first_bigiq = None

    def set_up(self):
        """Set up environment"""
        # check all bigiqs licensed and active before starting
        self.check_device_state(['active'])

        self._init_connections()

        all_devices = []
        for bigiq_index in range(0, self.cluster_args['num_bigiqs']):
            mylog('')
            bigiq_config = self.bigiq_configs[bigiq_index]

            ibig = self.icontrol_bigiqs[bigiq_index]

            # set hostname
            name = hostname_from_address(bigiq_config['mgmt_addr'])
            self.set_device_hostname(ibig, name)
            mylog(name)

            all_devices.append(name)

        # sleep 90 to make sure we're ready
        mylog("wait 90 secs before continuing")
        sleep(90)

        self.save_configs()

        # check all bigiqs active/standby after clustering
        self.check_device_state(['active'])

    def _init_connections(self):
        """Initialize connections to BIG-IQs"""
        if not self.connected:
            icontrol_access_addr = []
            for bigiq_index in range(0, len(self.bigiq_configs)):
                bigiq_config = self.bigiq_configs[bigiq_index]
                icontrol_access_addr.append(bigiq_config['floating_ip_addr'])

            icontrol_creds = {'username': 'admin',
                              'password': 'admin'}

            for bigiq_index in range(0, self.cluster_args['num_bigiqs']):
                if not hasattr(self.connected_by_access_addr,
                               icontrol_access_addr[bigiq_index]):
                    bigiq_to_add = bigip_icontrol.BigIP(
                        icontrol_access_addr[bigiq_index],
                        icontrol_creds['username'],
                        icontrol_creds['password'],
                        timeout=5,
                        address_isolation=True)
                    ic_access_addr = icontrol_access_addr[bigiq_index]
                    self.connected_by_access_addr[ic_access_addr] = \
                        bigiq_to_add
                    self.icontrol_bigiqs.append(bigiq_to_add)
                    if bigiq_index is 0:
                        self.first_bigiq = bigiq_to_add
                    mylog('Connected to ' + icontrol_access_addr[bigiq_index])
            self.connected = True

    def check_device_state(self, failover_states):
        """Helper to check device state"""
        check_state = BigIpCheckState(
            self.bigiq_configs, product_name="BIG-IQ")
        check_state.check_device_state(failover_states)

    def save_configs(self):
        """Save BIG-IQ configs"""
        mylog('Saving Configs...')
        for bigiq_index in range(self.cluster_args['num_bigiqs']):
            ibig = self.icontrol_bigiqs[bigiq_index]
            mylog('Saving bigiq%d' % (bigiq_index+1))
            try:
                ibig.cluster.save_config()
            # pylint: disable=broad-except
            # retry on failure
            except Exception, exception:
                mylog('ERROR: Saving bigiq%d. Waiting 30 secs for retry. '
                      'exception: %s' % (bigiq_index+1, str(exception)))
                sleep(30)
                ibig.cluster.save_config()
            # pylint: enable=bare-except
        mylog('Configs Saved.')

    def set_device_hostname(self, ibig, name):
        """Set device hostname"""
        mylog('sleep 2 blindly attempting to avoid exception on set_hostname')
        sleep(2)
        mylog('set folder to /Common blindly attempting to avoid '
              'exception on set_hostname')
        ibig.system.set_folder('/Common')
        mylog('set hostname: ' + name)
        ibig.system.set_hostname(name)
        check_device_hostname(ibig, name)
        if self.cluster_args['ha_type'] == 'standalone':
            mylog('sleep 10 to allow time for hostname')
        else:
            mylog('sleep 10 to avoid exception on trust reset ?')
        sleep(10)


def check_device_hostname(ibig, name, retry_delay=1):
    """Check device hostname has been set"""
    mylog('sleep 2 blindly prior to checking hostname')
    sleep(2)
    for _ in range(0, 30):
        try:
            mylog('set folder to /Common blindly attempting to avoid '
                  'exception on get_hostname')
            ibig.system.set_folder('/Common')
            mylog('check hostname: ' + name)
            hostname = ibig.system.get_hostname()
            if hostname == name:
                mylog('host name set')
                return
        # pylint: disable=broad-except
        except Exception, exception:
            mylog('Eating exception - %s' % exception)
        # pylint: enable=broad-except
        mylog('Sleep %d seconds.' % retry_delay)
        sleep(retry_delay)
    raise Exception('Hostname was not set to %s' % name)


def hostname_from_address(address):
    """Address-based hostname"""
    return 'host-' + address.replace('.', '-') + '.openstacklocal'


if __name__ == '__main__':
    # pylint: disable=broad-except
    # Okay to catch Exception at top level
    try:
        PARSER = argparse.ArgumentParser()
        PARSER.add_argument('--bigiq-image',
                            help='BIG-IQ Image to use.')
        PARSER.add_argument('--ha-type',
                            default='standalone',
                            help='standalone, pair, or scalen')
        PARSER.add_argument('--num-bigiqs',
                            type=int,
                            default=1,
                            help='Number of bigiqs to cluster')
        PARSER.add_argument('--bigiq-floating-ip-addr-list',
                            nargs='+',
                            help='List of bigiq floating ips (NATs) used to \
                                  access bigiqs.',
                            required=True)
        PARSER.add_argument('--bigiq-mgmt-addr-list',
                            nargs='+',
                            help='List of bigiq management addresses.',
                            required=True)
        ARGS = PARSER.parse_args()

        if (len(ARGS.bigiq_floating_ip_addr_list) != ARGS.num_bigiqs) or \
           (len(ARGS.bigiq_mgmt_addr_list) != ARGS.num_bigiqs):
            raise Exception('Number of entries in address lists should '
                            'match number of BIG-IQs (%d).' % ARGS.num_bigiqs)

        BIGIQ_CONFIGS = []
        for BIGIQ_INDEX in range(0, ARGS.num_bigiqs):
            BIGIQ_CONFIG = {}
            BIGIQ_CONFIG['name'] = 'bigiq%d' % (BIGIQ_INDEX+1)
            BIGIQ_CONFIG['floating_ip_addr'] = \
                ARGS.bigiq_floating_ip_addr_list[BIGIQ_INDEX]
            BIGIQ_CONFIG['mgmt_addr'] = \
                ARGS.bigiq_mgmt_addr_list[BIGIQ_INDEX]

            BIGIQ_CONFIGS.append(BIGIQ_CONFIG)

        BIGIQ_CLUSTER_GENERIC = BigIqClusterGeneric(ARGS.bigiq_image,
                                                    ARGS.ha_type,
                                                    ARGS.num_bigiqs,
                                                    BIGIQ_CONFIGS)
        BIGIQ_CLUSTER_GENERIC.set_up()
    except Exception, exception:
        mylog('Exception: %s' % str(exception))
        import traceback
        traceback.print_exc()
        exit(1)
    exit(0)
    # pylint: enable=broad-except
