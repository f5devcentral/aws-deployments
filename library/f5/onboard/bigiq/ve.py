#!/usr/bin/env python
"""Deploy BIG-IQ VE on OpenStack."""
import sys
import os.path

top_dir = os.path.join(os.path.dirname(__file__), '../../..')
top_dir = os.path.abspath(top_dir)
sys.path.insert(0, top_dir)
HOMEDIR = os.path.expanduser("~")

from f5.common.util import get_cmd_output
ODK_DIR = get_cmd_output(['bash', '-c', 'source odk-utils;echo $ODK_DIR'])[0]
sys.path.insert(0, ODK_DIR+'/python')

import argparse
import json
import requests
import time
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

BIG_IQ_FLAVOR = {'name': 'm1.bigiq',
                 'ram': 4096,
                 'vcpus': 2,
                 'disk': 55}


class BigiqVE(object):
    """Bigiq VE"""
    def __init__(self, admin_creds):
        self.nova_admin = NovaLib(admin_creds)

        self.nova_admin.create_flavor(
            BIG_IQ_FLAVOR['name'], BIG_IQ_FLAVOR['ram'],
            BIG_IQ_FLAVOR['vcpus'], BIG_IQ_FLAVOR['disk'])

        self.neutron_floating_ip_admin = NeutronFloatingIpLib(admin_creds)
        self.neutron_network_admin = NeutronNetworkLib(admin_creds)

        ext_network_def = get_ext_network_def(network_index=1)
        self.ext_net = self.neutron_network_admin.get_network(
            ext_network_def['network_name'])

        self.bigiq_net_def = {}
        network_index = 1
        for logical_net_name in ['mgmt', 'external', 'internal']:
            self.bigiq_net_def[logical_net_name] = \
                get_network_def(admin_creds.tenant_name,
                                network_index=network_index)
            self.bigiq_net_def[logical_net_name]['network_name'] = \
                'bigiq_%s' % logical_net_name

    def build_instance_nic_list(self):
        """Create nics array"""
        nics = []
        for logical_net_name in ['mgmt', 'external', 'internal']:
            net_name = self.bigiq_net_def[logical_net_name]['network_name']
            net = self.neutron_network_admin.get_network(net_name)
            nics.append({'net-id': net['id']})
        return nics

    def set_up(self, floating_ip_retry=60):
        """Set up environment"""

        nics = self.build_instance_nic_list()
        instances = []
        for bigiq_index in range(ARGS.bigiq_index,
                                 ARGS.bigiq_index + ARGS.num_bigiqs):
            userdata_file = open(
                HOMEDIR+'/.f5-onboard/tmp/startup_metadata_bigiq_%d.json' %
                (bigiq_index))
            userdata = userdata_file.read()
            userdata_file.close()
            instance_name = 'bigiq%d' % bigiq_index
            instances.append(self.nova_admin.create_instance(
                name=instance_name, image_name=ARGS.bigiq_image,
                flavor_name=BIG_IQ_FLAVOR['name'], nics=nics,
                userdata=userdata))

        floating_ip_addrs = ''
        for instance in instances:
            # Create floating ip and test connectivity
            port = self.neutron_network_admin.wait_instance_port(
                instance, self.bigiq_net_def['mgmt']['network_name'])
            floating_ip_addr = self.neutron_floating_ip_admin.\
                associate_port_floating_ip(self.ext_net, port['id'])
            if not test_connectivity(floating_ip_addr, PORT_SSH,
                                     floating_ip_retry):
                raise Exception('Instance connectivity test failed.')
            if floating_ip_addrs:
                floating_ip_addrs += (','+floating_ip_addr)
            else:
                floating_ip_addrs = floating_ip_addr

            # Automate the setting of the address to use for discovery on
            # the BIG-IQ. If we don't set it then we will get a 400 error
            # when we try to create cloud connectors. This is because a
            # device group is created for the cloud connector which then
            # tries to add the BIG-IQ. Adding the BIG-IQ to the device group
            # fails as the address to use for discovery/communication isn't
            # yet set.
            floating_ip = self.neutron_floating_ip_admin.\
                get_floating_ip(floating_ip_addr)

            self.set_discovery_address(floating_ip_addr,
                                       floating_ip['fixed_ip_address'])

        statefile = open(('%s/.f5-onboard/tmp/bigiq-addrs' % HOMEDIR), 'w')
        statefile.write(floating_ip_addrs)
        statefile.close()

    def set_discovery_address(
            self, floating_ip_addr, discovery_addr, retry_count=90):
        """Set the discovery address of the BIG-IQ

        Setting the discovery address of the BIG-IQ enables it to discovery
        other devices as well sustain communication with the devices it
        discovered.

        The local discovery address of the BIG-IQ has an OpenStack floating
        IP associated with it so that it can communicate with other devices
        outside of its network.

        :param string floating_ip_addr: Publicly routable discovery address
        :param string discovery_addr: Local (to OpenStack) discovery address
        :param integer retry_count: Amount of times to retry setting the
                                    discovery address should the REST endpoint
                                    not be up yet.
        """
        bigiq_creds = {'username': 'admin',
                       'password': 'admin'}

        http_session = requests.Session()
        http_session.auth = (bigiq_creds['username'], bigiq_creds['password'])
        http_session.verify = False
        http_session.headers.update({'Content-Type': 'application/json'})

        # We send a PUT request to the DiscoveryConfigWorker @
        # /mgmt/shared/identified-devices/config/discovery to set the discovery
        # address. It expects a body in the form of:
        #
        # { "discoveryAddress" : "10.10.10.10" }
        url = 'https://' + floating_ip_addr + \
            '/mgmt/shared/identified-devices/config/discovery'

        body = {'discoveryAddress': discovery_addr}

        # We typically will set the discovery address of the BIG-IQ after the
        # BIG-IQ is provisioned in OpenStack. More likely than not requests
        # we send to the REST endpoint, restjavad, will fail as the process
        # isn't yet up. We will attempt to make this request several times as
        # it could take restjavad some time to come up.
        #
        # There are two failures we need to account for when making requests
        # knowing that restjavad isn't yet up.
        #
        # The first is our connection being refused as the Nginx server isn't
        # yet up to process connections being made on port 443.
        #
        # The second are error status codes that we may receive as Nginx
        # accepted our connection and passed it along to the REST endpoint but
        # restjavad isn't yet up or its workers aren't yet fully started.
        for count in range(retry_count + 1):
            try:
                response = http_session.put(url, json.dumps(body))
                response.raise_for_status()

                self.neutron_network_admin.print_context.debug(
                    'Attempt %s passed.', str(count + 1))

                return
            # ConnectionError is a result of our connection being refused as
            # the Nginx server isn't up yet. HTTPError are bad status codes
            # from restjavad not being up yet or its workers aren't fully
            # started.
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError) as requests_exception:
                if count == retry_count:
                    raise requests_exception

                if not count % 10:
                    self.neutron_network_admin.print_context.debug(
                        'Attempt %s failed.', str(count + 1))

                time.sleep(1)

    def tear_down(self):
        """Tear down environment"""
        for bigiq_index in range(ARGS.bigiq_index,
                                 ARGS.bigiq_index + ARGS.num_bigiqs):
            instance_name = 'bigiq%d' % bigiq_index
            instance = self.nova_admin.get_instance(instance_name)
            if instance:
                port = self.neutron_network_admin.get_instance_port(
                    instance, self.bigiq_net_def['mgmt']['network_name'])
                if port:
                    floating_ip_addr = self.neutron_floating_ip_admin.\
                        get_port_floating_ip_addr(port['id'])
                    if floating_ip_addr:
                        self.neutron_floating_ip_admin.delete_floating_ip(
                            floating_ip_addr)

                self.nova_admin.delete_instance(instance)


if __name__ == '__main__':
    # pylint: disable=broad-except
    # Okay to catch Exception at top level
    try:
        PARSER = argparse.ArgumentParser(parents=[ADMIN_CREDS_PARSER,
                                                  BASE_PARSER,
                                                  CRUD_PARSER])
        PARSER.add_argument('--bigiq-image',
                            help='BIQ-IP image to use.')
        PARSER.add_argument('--bigiq-index',
                            type=int,
                            default=1,
                            help='Starting index of BIG-IQ to act on. \
                                  The first is 1.')
        PARSER.add_argument('--num-bigiqs',
                            type=int,
                            default=1,
                            help='How many BIG-IQs to launch.')
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

        BIGIQ_VE = BigiqVE(CREDS)
        if not ARGS.clean_up_only:
            BIGIQ_VE.set_up()
        if not ARGS.no_clean_up:
            BIGIQ_VE.tear_down()
    except Exception, exception:
        import traceback
        traceback.print_exc()
        exit(1)
    exit(0)
    # pylint: enable=broad-except
