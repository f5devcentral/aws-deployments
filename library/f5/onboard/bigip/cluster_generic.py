#!/usr/bin/env python
"""Cluster BIG-IPs on OpenStack."""
import sys
import os.path
top_dir = os.path.join(os.path.dirname(__file__), '../../../..')
top_dir = os.path.abspath(top_dir)
sys.path.insert(0, top_dir)

import argparse
import datetime

from time import sleep

from f5.bigip.bigip import BigIP
from f5.onboard.bigip.lib.check_state import BigIpCheckState


def mylog(msg):
    """Logger"""
    print '%s: %s' % (datetime.datetime.now().strftime('%b %d %H:%M:%S'), msg)


class BigIpClusterGeneric(object):
    """BigIp Generic Clustering"""
    def __init__(self, bigip_image, ha_type,
                 num_bigips, bigip_configs, cluster_name):
        self.cluster_args = {}
        self.cluster_args['cluster_name'] = cluster_name
        self.cluster_args['ha_type'] = ha_type
        self.cluster_args['num_bigips'] = num_bigips

        self.bigip_configs = bigip_configs
        self.icontrol_bigips = []
        self.connected = False
        self.connected_by_access_addr = {}
        self.first_bigip = None

    def set_up(self):
        """Set up environment"""
        # check all bigips licensed and active before starting
        self.check_device_state(['active'])

        self._init_connections()

        all_devices = []
        for bigip_index in range(0, self.cluster_args['num_bigips']):
            mylog('')
            bigip_config = self.bigip_configs[bigip_index]

            ibig = self.icontrol_bigips[bigip_index]

            # set hostname
            self.domain_name = \
                ibig.system.get_hostname().partition('.')[2]
            name = hostname_from_address(bigip_config['mgmt_addr'],
                                         self.domain_name)
            self.set_device_hostname(ibig, name)
            mylog(name)

            # turn router domain strictness off
            mylog('turning route domain strictness turned off')
            ibig.route.set_strict_state(
                name='0', folder='Common', state='disabled')
            mylog('route domain strictness turned off')

            if self.cluster_args['ha_type'] == 'standalone':
                continue

            # reset trust
            mylog('resetting trust: ' + name)
            ibig.device.reset_trust(name)
            mylog('sleep 20 after trust reset before setting addresses')
            sleep(20)

            # set BIG-IP failover addresses (assigned by openstack)
            mylog('set configsync addr: ' + bigip_config['ha_addr'])
            ibig.device.set_configsync_addr(bigip_config['ha_addr'])

            mylog('set primary mirror: ' + bigip_config['mirror_addr'])
            ibig.device.set_primary_mirror_addr(bigip_config['mirror_addr'])

            mylog('set secondary mirror: ' + bigip_config['ha_addr'])
            ibig.device.set_secondary_mirror_addr(bigip_config['ha_addr'])

            mylog('set failover heartbeat addrs: ' + str([
                bigip_config['ha_addr'], bigip_config['mirror_addr'],
                bigip_config['mgmt_addr']]))
            ibig.device.set_failover_addrs([
                bigip_config['ha_addr'], bigip_config['mirror_addr'],
                bigip_config['mgmt_addr']])
            all_devices.append(name)

        # sleep 90 to make sure we're ready
        if self.cluster_args['ha_type'] == 'standalone':
            mylog("wait 90 secs before continuing")
        else:
            mylog("wait 90 secs for trust to be reset before adding peers")
        sleep(90)
        if self.cluster_args['ha_type'] != 'standalone':
            mylog('This delay is attempting fix a problem where a peer shows '
                  'as uninitialized')
            mylog('trust-domain and is rejected by a device adding it as a '
                  'peer')
            mylog('The theory being that the trust domain reset done above '
                  'may not finish right away.')

        # create cluster of peers
        if self.cluster_args['ha_type'] != 'standalone':
            tg_list = []
            if self.cluster_args['ha_type'] == 'scalen':
                tg_list = create_tg_list(all_devices)
            self.cluster_devices(all_devices, tg_list)

        self.save_configs()
        if self.cluster_args['ha_type'] == 'scalen':
            self.set_tgs_initial_devices(tg_list, all_devices)
            mylog('Failovers completed.')

        # check all bigips active/standby after clustering
        if self.cluster_args['ha_type'] == 'scalen':
            self.check_device_state(['active'])
        elif self.cluster_args['ha_type'] == 'pair':
            self.check_device_state(['active',
                                     'standby'])

    def _init_connections(self):
        """Initialize connections to BIG-IPs"""
        if not self.connected:
            icontrol_access_addr = []
            for bigip_index in range(0, len(self.bigip_configs)):
                bigip_config = self.bigip_configs[bigip_index]
                icontrol_access_addr.append(bigip_config['floating_ip_addr'])

            for bigip_index in range(0, self.cluster_args['num_bigips']):
                if not hasattr(self.connected_by_access_addr,
                               icontrol_access_addr[bigip_index]):
                    bigip_to_add = BigIP(
                        icontrol_access_addr[bigip_index],
                        bigip_config['username'], bigip_config['password'],
                        timeout=5, address_isolation=True)
                    ic_access_addr = icontrol_access_addr[bigip_index]
                    self.connected_by_access_addr[ic_access_addr] = \
                        bigip_to_add
                    self.icontrol_bigips.append(bigip_to_add)
                    if bigip_index is 0:
                        self.first_bigip = bigip_to_add
                    mylog('Connected to ' + icontrol_access_addr[bigip_index])
            self.connected = True

    def sync_with_retries(self, device_group, force_now=False, attempts=4,
                          retry_delay=130):
        """Sync cluster"""
        for attempt in range(1, attempts + 1):
            mylog('Syncing Cluster... attempt %d of %d' % (attempt, attempts))
            try:
                if attempt != 1:
                    force_now = False
                self.first_bigip.cluster.sync(
                    device_group, force_now=force_now)
                mylog('Cluster synced.')
                return
            # pylint: disable=bare-except
            # retry/raise on failure
            except:
                mylog('ERROR: Cluster sync failed.')
                if attempt == attempts:
                    raise
                mylog('Wait another %d seconds for devices to recover from '
                      'failed sync.' % retry_delay)
                sleep(retry_delay)
            # pylint: enable=bare-except

    def check_device_state(self, failover_states):
        """Helper to check device state"""
        check_state = BigIpCheckState(self.bigip_configs)
        check_state.check_device_state(failover_states)

    def wait_for_trust_group_sync(self, ok_status="In Sync", retry_delay=10):
        """Wait until trust group is in sync"""
        mylog('Wait until device_trust_group is in sync...')
        for _ in range(0, 60):
            try:
                status = self.first_bigip.cluster.get_sync_status()
                color = self.first_bigip.cluster.get_sync_color()
                mylog('device_trust_group sync status: %s, %s' %
                      (color, status))
                if color == 'green' and status == ok_status:
                    mylog('device_trust_group is in sync.')
                    return
            # pylint: disable=broad-except
            except Exception, exception:
                mylog('Eating exception - %s' % exception)
            # pylint: enable=broad-except
            mylog('Sleep %d seconds.' % retry_delay)
            sleep(retry_delay)

        raise Exception('device_trust_group not in sync - status: %s, %s' %
                        (color, status))

    def cluster_devices(self, all_devices, tg_list):
        """Cluster BIG-IPs"""
        self.wait_for_trust_group_sync('Standalone')

        for bigip_index in range(1, self.cluster_args['num_bigips']):
            bigip_config = self.bigip_configs[bigip_index]

            peer_name = hostname_from_address(bigip_config['mgmt_addr'],
                                              self.domain_name)
            mylog("")
            mylog("Adding peer %s" % peer_name)
            try:
                self.first_bigip.cluster.add_peer(
                    peer_name,
                    bigip_config['mgmt_addr'],
                    bigip_config['username'],
                    bigip_config['password']
                )
            # pylint: disable=bare-except
            # retry on failure
            # pylint: disable=broad-except
            except Exception, exception:
                mylog('Eating exception - %s' % exception)
            # pylint: enable=broad-except
            #except:
                mylog("ERROR: add_peer failed. Trying again.")
                sleep(30)
                self.first_bigip.cluster.add_peer(
                    peer_name,
                    bigip_config['mgmt_addr'],
                    bigip_config['username'],
                    bigip_config['password']
                )
            # pylint: enable=bare-except
            mylog("Added peer %s" % peer_name)
            if self.cluster_args['ha_type'] == 'scalen':
                mylog("wait 5 secs for peer to add")
                sleep(5)

            # wait until trust group is in sync
            self.wait_for_trust_group_sync()

        self.first_bigip.cluster.create(
            self.cluster_args['cluster_name'], True)
        if self.cluster_args['ha_type'] == 'scalen':
            mylog("wait 5 secs for create device group to sync")
            sleep(5)
        self.first_bigip.cluster.add_devices(
            self.cluster_args['cluster_name'], all_devices)

        if self.cluster_args['ha_type'] == 'scalen':
            sleep_time = 60
        else:
            sleep_time = 30
        mylog('Sleeping %d seconds so cluster can connect,'
              ' so we can sync without going haywire' % sleep_time)
        sleep(sleep_time)

        force_now = False
        # v11.5.0 doesn't go to In Sync status unless you initiate a sync
        if '11.5' in self.first_bigip.system.get_version():
            force_now = True
        self.sync_with_retries(
            self.cluster_args['cluster_name'], force_now=force_now)

        if self.cluster_args['ha_type'] == 'scalen':
            create_tg = self.first_bigip.cluster.create_traffic_group
            for tg_name in tg_list[1:]:
                create_tg(name=tg_name)
            update_tg = self.first_bigip.cluster.update_traffic_group
            for tg_index in range(len(tg_list)):
                ha_order = get_tg_ha_order(tg_index, all_devices)
                update_tg(name=tg_list[tg_index], ha_order=ha_order)
            mylog('Sleep 30 seconds for traffic groups to sync.')
            sleep(30)
            self.sync_with_retries('openstack.bigip.cluster')
        mylog('Clustering completed.')

    def save_configs(self):
        """Save BIG-IP configs"""
        mylog('Saving Configs...')
        for bigip_index in range(self.cluster_args['num_bigips']):
            ibig = self.icontrol_bigips[bigip_index]
            bigip_name = self.bigip_configs[bigip_index]['name']
            self.bigip_configs
            mylog('Saving %s' % bigip_name)
            try:
                ibig.cluster.save_config()
            # pylint: disable=broad-except
            # retry on failure
            except Exception, exception:
                mylog('ERROR: Saving %s. Waiting 30 secs for retry. '
                      'exception: %s' % (bigip_name, str(exception)))
                sleep(30)
                ibig.cluster.save_config()
            # pylint: enable=bare-except
        mylog('Configs Saved.')

    def set_tgs_initial_devices(self, tg_list, device_list):
        """Set initial device for all traffic groups"""
        for tg_index in range(len(tg_list)):
            for bigip_index in range(self.cluster_args['num_bigips']):
                ibig = self.icontrol_bigips[bigip_index]
                set_tg_initial_device(ibig, bigip_index, tg_list[tg_index],
                                      tg_index, device_list)

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


def hostname_from_address(address, domain):
    """Address-based hostname"""
    return 'host-' + address.replace('.', '-') + '.' + domain


def create_tg_list(all_devices):
    """Create a list of traffic group names based on the number of devices"""
    max_traffic_groups = 15
    targets = len(all_devices)
    if targets == 2:
        num_traffic_groups = 2
    elif targets == 3:
        num_traffic_groups = 6
    else:
        num_traffic_groups = targets
        while num_traffic_groups * (targets - 1) < max_traffic_groups:
            targets -= 1
            num_traffic_groups = num_traffic_groups * targets
    tg_list = []
    for tg_index in range(1, num_traffic_groups + 1):
        tg_list.append('traffic-group-%d' % tg_index)
    return tg_list


def get_tg_ha_order(tg_index, device_list):
    """Get ha order for a traffic group"""
    num_devices = len(device_list)
    # Descend a tree where each child node represents a
    # failure of a particular device. Use an incrementing
    # number to represent a path index that is used
    # to control the descent down the tree.
    # The key is to use the least significant bits of the
    # incrementing index to represent the most significant (top most)
    # branches of the tree, thereby producing a traversal
    # that is even balanced across the tree.
    order = []
    traverse_by_index(num_devices,
                      order,
                      range(1, num_devices + 1),
                      tg_index, 0)
    ha_order = []
    for i in range(num_devices):
        ha_order.append(device_list[order[i] - 1])
    return ha_order


def set_tg_initial_device(bigip, bigip_index, traffic_group, tg_index,
                          device_list):
    """Set initial device for a traffic group"""
    num_devices = len(device_list)
    order = []
    traverse_by_index(
        num_devices, order, range(1, num_devices + 1), tg_index, 0)
    # don't try to go standby for tgs that should be active on the bigip
    # we are talking to
    if order[0] != bigip_index + 1:
        initial_device = device_list[order[0] - 1]
        mylog('fail group %s on %s to %s' %
              (traffic_group, bigip_index + 1, initial_device))
        bigip.system.force_to_standby(traffic_group)


# pylint: disable=invalid-name
# using 'n'
def base10_to_n_descend(num, n, minlen=0):
    """convert a number to base N (descending)
       which is a number that is base N
       for the least significant digit and
       base N-1 for the next least and so on."""

    new_num_string = ''
    current = num
    while current != 0:
        remainder = current % n
        remainder_string = str(remainder)
        new_num_string = remainder_string + new_num_string
        current = current / n
        n -= 1
    while len(new_num_string) < minlen:
        new_num_string = '0' + new_num_string
    return new_num_string
# pylint: enable=invalid-name


def traverse_by_index(num_targets, order, remaining, path_index, level):
    """traverse a tree that represents all possible
       failure scenarios.
       A base N number to control the tree traversal."""
    descent_path = base10_to_n_descend(path_index, num_targets, num_targets)
    next_branch = int(descent_path[(level + 1) * -1])
    next_branch_target = remaining[next_branch]
    order.append(next_branch_target)
    new_remaining = list(remaining)
    new_remaining.remove(next_branch_target)
    if level == num_targets - 1:
        return
    else:
        traverse_by_index(
            num_targets, order, new_remaining, path_index, level + 1)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    # pylint: disable=broad-except
    # Okay to catch Exception at top level
    try:
        PARSER = argparse.ArgumentParser()
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
        PARSER.add_argument('--bigip-floating-ip-addr-list',
                            nargs='*',
                            help='List of bigip floating ips (NATs) used to \
                                  access bigips.',
                            required=True)
        PARSER.add_argument('--bigip-mgmt-addr-list',
                            nargs='+',
                            help='List of bigip management addresses.',
                            required=True)
        PARSER.add_argument('--bigip-ha-addr-list',
                            nargs='+',
                            help='List of bigip HA addresses.',
                            required=True)
        PARSER.add_argument('--bigip-mirror-addr-list',
                            nargs='+',
                            help='List of bigip mirroring addresses.',
                            required=True)

        # Added implicitly defined attributes
        PARSER.add_argument(
            '--bigip-cluster-name',
            metavar='bigip-cluster-name',
            default='openstack.bigip.cluster',
            help='Device service group name.'
        )
        PARSER.add_argument(
            '--bigip-name',
            metavar='bigip-name',
            default='bigip',
            help='Prefix to use for BIG-IP name, postfixed by the index.'
        )
        PARSER.add_argument(
            '--bigip-icontrol-username',
            metavar='bigip-icontrol-username',
            default='admin',
            help='Username to use for iControl access.'
        )
        PARSER.add_argument(
            '--bigip-icontrol-password',
            metavar='bigip-icontrol-password',
            default='admin',
            help='Password to use for iControl access.'
        )
        ARGS = PARSER.parse_args()

        if (len(ARGS.bigip_floating_ip_addr_list) != ARGS.num_bigips) or \
           (len(ARGS.bigip_mgmt_addr_list) != ARGS.num_bigips) or \
           (len(ARGS.bigip_ha_addr_list) != ARGS.num_bigips) or \
           (len(ARGS.bigip_mirror_addr_list) != ARGS.num_bigips):
            raise Exception('Number of entries in address lists should '
                            'match number of BIG-IPs (%d).' % ARGS.num_bigips)

        BIGIP_CONFIGS = []
        for BIGIP_INDEX in range(0, ARGS.num_bigips):
            BIGIP_CONFIG = {}
            BIGIP_CONFIG['username'] = ARGS.bigip_icontrol_username
            BIGIP_CONFIG['password'] = ARGS.bigip_icontrol_password
            BIGIP_CONFIG['name'] = '%s%d' % (ARGS.bigip_name, BIGIP_INDEX + 1)
            BIGIP_CONFIG['floating_ip_addr'] = \
                ARGS.bigip_floating_ip_addr_list[BIGIP_INDEX]
            BIGIP_CONFIG['mgmt_addr'] = \
                ARGS.bigip_mgmt_addr_list[BIGIP_INDEX]
            BIGIP_CONFIG['ha_addr'] = \
                ARGS.bigip_ha_addr_list[BIGIP_INDEX]
            BIGIP_CONFIG['mirror_addr'] = \
                ARGS.bigip_mirror_addr_list[BIGIP_INDEX]

            BIGIP_CONFIGS.append(BIGIP_CONFIG)

        BIGIP_CLUSTER_GENERIC = BigIpClusterGeneric(
            ARGS.bigip_image,
            ARGS.ha_type,
            ARGS.num_bigips,
            BIGIP_CONFIGS,
            ARGS.bigip_cluster_name
        )
        BIGIP_CLUSTER_GENERIC.set_up()
    except Exception, exception:
        mylog('Exception: %s' % str(exception))
        import traceback
        traceback.print_exc()
        exit(1)
    exit(0)
    # pylint: enable=broad-except


if __name__ == "__main__":
    sys.exit(main())
