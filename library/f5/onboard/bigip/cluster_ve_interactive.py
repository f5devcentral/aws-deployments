#!/usr/bin/env python

import os
import sys
import json
import argparse
import termios  # @UnresolvedImport
import fcntl
import getpass
import prettytable
import time

from uuid import UUID
from distutils.util import strtobool
from odk.lib.keystone import KeystoneLib
from odk.lib.nova import NovaLib
from odk.lib.neutron import NeutronNetworkLib
from odk.lib.glance import GlanceLib
import odk.lib.client as odkclient

from odk.setup.common.args import ADMIN_CREDS_PARSER
from odk.setup.common.args import TENANT_CREDS_PARSER
from odk.setup.common.args import BASE_PARSER
from odk.setup.common.args import CRUD_PARSER
from odk.setup.common.args import set_base_globals
from odk.setup.common.args import set_crud_globals
from odk.setup.common.util import get_creds

from f5.onboard.bigip.ve import BigipVE as AdminVE
from f5.onboard.bigip.ve_tenant import BigipVE as TenantVE
from f5.onboard.bigip.cluster_generic import BigIpClusterGeneric
from novaclient.exceptions import NotFound


class VECLI():

    _discovered_tmos_disk_images = {}
    _discovered_tmos_volume_images = {}
    _discovered_tmos_flavors = {}
    _flavor_list = []

    def __init__(self, creds):
        self._creds = creds
        self._keystone = KeystoneLib(creds['admin'], creds['tenant'])
        self._nova = NovaLib(
            admin_creds=creds['admin'],
            tenant_creds=creds['tenant']
        )
        self._neutron = NeutronNetworkLib(creds['admin'], creds['tenant'])
        self._glance = GlanceLib(creds['admin'], creds['tenant'])

    def _getch(self):
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
        try:
            while 1:
                try:
                    c = sys.stdin.read(1)
                    break
                except IOError:
                    pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
        sys.stdout.write('\n')
        return c

    def _discover_tmos_images(self, tenant_id=None):
        self._discovered_tmos_disk_images = {}
        self._discovered_tmos_volume_images = {}
        self._flavors_list = []
        filters = {'properties': {'os_vendor': 'f5_networks'}}
        glance = self._glance.glance_client
        for image in list(glance.images.list(filters=filters)):
            if tenant_id:
                if not image.owner == tenant_id or \
                   not image.is_public:
                    continue
            if image.properties['os_type'] == 'f5bigip_datastor':
                self._discovered_tmos_volume_images[image.id] = image
            else:
                self._discovered_tmos_disk_images[image.id] = image
            if 'nova_flavor' in image.properties:
                self._flavor_list.append(image.properties['nova_flavor'])

    def _discover_tmos_flavors(self):
        nova = self._nova.nova_client
        for flavor in list(nova.flavors.list()):
            metadata = flavor.get_keys()
            if 'flavor_vendor' in metadata and \
               metadata['flavor_vendor'] == 'f5_networks':
                self._discovered_tmos_flavors[flavor.id] = flavor

    def _discover_tmos_instances_by_image(self, tenant_id=None):
        if not self._discovered_tmos_disk_images:
            self._discover_tmos_images()
        nova = self._nova.nova_client
        servers = list(
            nova.servers.list(
                detailed=True,
                search_opts={
                    'os_vendor': 'f5_networks',
                    'all_tenants': 1
                }
            )
        )
        tmos_servers = []
        for server in servers:
            if tenant_id and \
               not server.tenant_id == tenant_id:
                continue
            if server.image['id'] in \
               self._discovered_tmos_disk_images.keys():
                tmos_servers.append(server)
        return tmos_servers

    def _discover_tmos_instances_by_os_vendor(self, tenant_id=None):
        nova = self._nova.nova_client
        servers = list(
            nova.servers.list(
                detailed=True,
                search_opts={
                    'os_vendor': 'f5_networks',
                    'all_tenants': 1
                }
            )
        )
        tmos_servers = []
        for server in servers:
            if tenant_id and \
               not server.tenant_id == tenant_id:
                continue
            if 'os_vendor' in server.metadata and \
               server.metadata['os_vendor'] == 'f5_networks':
                tmos_servers.append(server)
        return tmos_servers

    def _get_tmos_device_service_groups(self, tenant_id=None):
        existing_dsg = {}
        servers = self._discover_tmos_instances_by_os_vendor()
        for server in servers:
            if tenant_id and \
               not server.tenant_id == tenant_id:
                continue
            if 'f5_device_group' in server.metadata:
                dsg_name = server.metadata['f5_device_group']
                if dsg_name not in existing_dsg:
                    existing_dsg[dsg_name] = []
                existing_dsg[dsg_name].append(server)
        return existing_dsg

    def _get_security_group(self, group_name):
        nova = self._nova.nova_client
        return nova.security_groups.find(name=group_name)

    def _validate_basekey(self, basekey):
        if len(basekey) > 30 and basekey.count('-') > 3:
            return True
        else:
            return False

    def _resolve_disk_image_id(self, image):
        try:
            UUID(image, version=4)
            return image
        except ValueError:
            self._discover_tmos_images()
            for image_obj in self._discovered_tmos_disk_images.values():
                if image_obj.name == image:
                    return image_obj.id
            else:
                return None

    def _resolve_flavor_id(self, flavor):
        try:
            UUID(flavor, version=4)
            return flavor
        except ValueError:
            self._discover_tmos_flavors()
            for flavor_obj in self._discovered_tmos_flavors.values():
                if flavor_obj.name == flavor:
                    return flavor_obj.id
            else:
                return None

    def image_report(self, output_json=False):
        if output_json:
            return self._image_json_report()
        else:
            return self._image_report()

    def _image_report(self):
        self._discover_tmos_images()
        if self._discovered_tmos_disk_images or \
           self._discovered_tmos_volume_images:
            headings = ["ID", "Name", "Flavor", "Type"]
            x = prettytable.PrettyTable(headings)
            for col in headings:
                x.align[col] = 'l'
            di = self._discovered_tmos_disk_images
            for image_id in di:
                image_name = di[image_id].name
                if 'nova_flavor' in di[image_id].properties:
                    image_flavor = di[image_id].properties['nova_flavor']
                else:
                    image_flavor = 'None'
                if 'os_type' in di[image_id].properties:
                    image_type = di[image_id].properties['os_type']
                else:
                    image_type = 'Generic'
                x.add_row([image_id, image_name, image_flavor, image_type])
            vi = self._discovered_tmos_volume_images
            for image_id in vi:
                image_name = vi[image_id].name
                if 'nova_flavor' in vi[image_id].properties:
                    image_flavor = vi[image_id].properties['nova_flavor']
                else:
                    image_flavor = 'None'
                if 'os_type' in vi[image_id].properties:
                    image_type = vi[image_id].properties['os_type']
                else:
                    image_type = 'Generic'
                x.add_row([image_id, image_name, image_flavor, image_type])
            print x

    def _image_json_report(self):
        self._discover_tmos_images()
        if self._discovered_tmos_disk_images or \
           self._discovered_tmos_volume_images:
            di = self._discovered_tmos_disk_images
            disk_images = {}
            for image_id in di:
                image_name = di[image_id].name
                if 'nova_flavor' in di[image_id].properties:
                    image_flavor = di[image_id].properties['nova_flavor']
                else:
                    image_flavor = 'None'
                if 'os_type' in di[image_id].properties:
                    image_type = di[image_id].properties['os_type']
                else:
                    image_type = 'Generic'
                disk_images[image_id] = {}
                disk_images[image_id]['name'] = image_name
                disk_images[image_id]['flavor'] = image_flavor
                disk_images[image_id]['type'] = image_type
            vi = self._discovered_tmos_volume_images
            volume_images = {}
            for image_id in vi:
                image_name = vi[image_id].name
                if 'nova_flavor' in vi[image_id].properties:
                    image_flavor = vi[image_id].properties['nova_flavor']
                else:
                    image_flavor = 'None'
                if 'os_type' in vi[image_id].properties:
                    image_type = vi[image_id].properties['os_type']
                else:
                    image_type = 'Generic'
                volume_images[image_id] = {}
                volume_images[image_id]['name'] = image_name
                volume_images[image_id]['flavor'] = image_flavor
                volume_images[image_id]['type'] = image_type
            images = {'images': {'disk_images': disk_images,
                                 'volume_images': volume_images}}
            print json.dumps(images, indent=4, sort_keys=True)

    def instance_report(self, output_json=False):
        if output_json:
            return self._instance_json_report()
        else:
            return self._instance_report()

    def _instance_report(self):
        printed_servers = []
        image_servers = self._discover_tmos_instances_by_image()
        vendor_servers = self._discover_tmos_instances_by_os_vendor()
        if image_servers or vendor_servers:
            headings = ["ID", "Name", "Device Group",
                        "Flavor", "Image", "Status"]
            x = prettytable.PrettyTable(headings)
            for col in headings:
                x.align[col] = 'l'
            for server in image_servers:
                printed_servers.append(server.id)
                if server.flavor['id'] in self._discovered_tmos_flavors:
                    server_flavor = \
                        self._discovered_tmos_flavors[server.flavor['id']].name
                else:
                    server_flavor = 'Unmanaged'
                if server.image['id'] in self._discovered_tmos_disk_images:
                    server_image = \
                        self._discovered_tmos_disk_images[
                            server.image['id']
                        ].name
                else:
                    server_image = 'Unmanaged'
                if 'f5_device_group' in server.metadata:
                    server_dsg = server.metadata['f5_device_group']
                    if 'f5_device_group_primary_device' in server.metadata:
                        if server.metadata[
                                'f5_device_group_primary_device'] == 'true':
                            server_dsg += ' (primary)'
                else:
                    server_dsg = 'None'
                x.add_row([server.id,
                           server.name,
                           server_dsg,
                           server_flavor,
                           server_image,
                           server.status])
            for server in vendor_servers:
                if server.id not in printed_servers:
                    printed_servers.append(server.id)
                    if server.flavor['id'] in self._discovered_tmos_flavors:
                        server_flavor = \
                            self._discovered_tmos_flavors[
                                server.flavor['id']
                            ].name
                    else:
                        server_flavor = 'Unmanaged'
                    server_image = 'Unmanaged'
                    if 'f5_device_group' in server.metadata:
                        server_dsg = server.metadata['f5_device_group']
                        if 'f5_device_group_primary_device' in server.metadata:
                            if server.metadata[
                               'f5_device_group_primary_device'] == 'true':
                                server_dsg += ' (primary)'
                    else:
                        server_dsg = 'None'
                    x.add_row([server.id,
                               server.name,
                               server_dsg,
                               server_flavor,
                               server_image,
                               server.status])
            print x

    def _instance_json_report(self):
        printed_servers = []
        image_servers = self._discover_tmos_instances_by_image()
        vendor_servers = self._discover_tmos_instances_by_os_vendor()
        if image_servers or vendor_servers:
            image_server = {}
            for server in image_servers:
                printed_servers.append(server.id)
                if server.flavor['id'] in self._discovered_tmos_flavors:
                    server_flavor = \
                        self._discovered_tmos_flavors[server.flavor['id']].name
                else:
                    server_flavor = 'None'
                if server.image['id'] in self._discovered_tmos_disk_images:
                    server_image = \
                        self._discovered_tmos_disk_images[
                            server.image['id']
                        ].name
                else:
                    server_image = 'None'
                if 'f5_device_group' in server.metadata:
                    server_dsg = server.metadata['f5_device_group']
                    if 'f5_device_group_primary_device' in server.metadata:
                        if server.metadata[
                                'f5_device_group_primary_device'] == 'true':
                            server_dsg_primary = True
                else:
                    server_dsg = 'None'
                    server_dsg_primary = False
                image_server[server.id] = {}
                image_server[server.id]['name'] = server.name
                image_server[server.id]['f5_device_service_group'] = server_dsg
                image_server[server.id]['f5_device_service_group_primary'] = \
                    server_dsg_primary
                image_server[server.id]['flavor'] = {'id': server.flavor['id'],
                                                     'name': server_flavor}
                image_server[server.id]['image'] = {'id': server.image.id,
                                                    'name': server_image}
                image_server[server.id]['status'] = server.status
            for server in vendor_servers:
                if server.id not in printed_servers:
                    image_server[server.id] = {}
                    if 'f5_device_group' in server.metadata:
                        server_dsg = server.metadata['f5_device_group']
                    if 'f5_device_group_primary_device' in server.metadata:
                        if server.metadata[
                                'f5_device_group_primary_device'] == 'true':
                            server_dsg_primary = True
                    else:
                        server_dsg = 'None'
                        server_dsg_primary = False
                    image_server[server.id]['name'] = server.name
                    image_server[server.id][
                        'f5_device_service_group'
                    ] = server_dsg
                    image_server[server.id][
                        'f5_device_service_group_primary'
                    ] = server_dsg_primary
                    image_server[server.id]['flavor'] = \
                        {'id': server.flavor['id'], 'name': 'None'}
                    image_server[server.id]['image'] = \
                        {'id': server.image['id'], 'name': 'None'}
                    image_server[server.id]['status'] = server.status
            servers = {'servers': image_server}
            print json.dumps(servers, indent=4, sort_keys=True)

    def build_policy_file(self, args):
        policies = {}
        policies['devicegroups'] = []
        policy = {}
        policies['devicegroups'].append(policy)

        need_dsg_name = True
        need_type = True
        need_tenant = True
        tenant_id = None
        tenant_name = None
        need_image = True
        need_key = True
        need_sec_group = True
        need_tmos_admin_password = True
        tmos_admin_password = None
        need_tmos_root_password = True
        tmos_root_password = None
        number_of_devices_needed = 0

        license_basekeys = []
        assigned_networks = []

        selected_image = None
        selected_flavor = None

        MAX_VIFS = 10
        need_mgmt_net = True
        mgmt_net = None
        need_ha_net = True
        ha_net = None
        need_vtep_net = False
        vtep_net = None

        indexed_networks = {}

        nova = self._nova.nova_client
        neutron = self._neutron.neutron_client

        print "\n\nDevice Service Group Policy Builder\n\n"

        try:
            dsgs = self._get_tmos_device_service_groups()
            while need_dsg_name:
                sys.stdout.write("New Device Service Group Name: ")
                dsg_name = sys.stdin.readline().strip()
                if dsg_name in dsgs:
                    print "WARNING! - %s already exists" % dsg_name
                    sys.stdout.write(
                        "Do you want me to delete the instances in %s? [y/n]: "
                        % dsg_name
                    )
                    del_dsg = strtobool(self._getch())
                    if del_dsg:
                        for server in dsgs[dsg_name]:
                            server.delete()
                        del dsgs[dsg_name]
                else:
                    need_dsg_name = False
                    policy['device_group'] = dsg_name
            if need_type:
                headings = ["No.", "Cluster Type", "Device Count"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                x.add_row([1, "Standalone", 1])
                x.add_row([2, "HA Pair", 2])
                x.add_row([3, "ScaleN", 4])
                print x
            while need_type:
                sys.stdout.write("Cluster Type? (1,2,3): ")
                cluster_type = int(sys.stdin.readline().strip())
                if cluster_type in [1, 2, 3]:
                    if cluster_type == 1:
                        policy['ha_type'] = 'standalone'
                        number_of_devices_needed = 1
                        need_ha_net = False
                    elif cluster_type == 2:
                        policy['ha_type'] = 'pair'
                        number_of_devices_needed = 2
                    elif cluster_type == 3:
                        policy['ha_type'] = 'scalen'
                        number_of_devices_needed = 4
                    need_type = False
            if need_tenant:
                if self._creds['admin']:
                    keystone = self._keystone.keystone_admin
                    tenants = keystone.projects.list()
                    if len(tenants) == 1:
                        policy['tenant'] = tenants[0].name
                        need_tenant = False
                    else:
                        headings = ["No.", "ID", "Tenant"]
                        x = prettytable.PrettyTable(headings)
                        for col in headings:
                            x.align[col] = 'l'
                        choices = {}
                        tenant_ids = {}
                        i = 1
                        for tenant in tenants:
                            if not tenant.name == 'service' and tenant.enabled:
                                choices[i] = tenant.name
                                tenant_ids[i] = tenant.id
                                x.add_row([i, tenant.id, tenant.name])
                                i = i + 1
                        print x
                else:
                    policy['tenant'] = self._creds['tenant'].tenant_name
                    policy['tenant_id'] = \
                        self._keystone.keystone_tenant.auth_tenant_id
                    need_tenant = False
            while need_tenant:
                sys.stdout.write("Tenant? (1..%d): " % len(choices))
                choice = int(sys.stdin.readline().strip())
                if choice in range(1, len(choices) + 1):
                    policy['tenant'] = choices[choice]
                    policy['tenant_id'] = tenant_ids[choice]
                    tenant_name = choices[choice]
                    tenant_id = tenant_ids[choice]
                    need_tenant = False

            tenant_id = policy['tenant_id']
            if self._creds['admin'] and \
               not policy['tenant'] == 'admin' and \
               not policy['tenant'] == self._creds['admin'].tenant_name:
                self._discover_tmos_images(tenant_id=tenant_id)
                self._creds['admin'].tenant_name = policy['tenant']
                nova = odkclient.get_nova_client(self._creds['admin'])
            if need_image:
                headings = ["No.", "ID", "Image"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                self._discover_tmos_images()
                choices = {}
                i = 1
                for image in self._discovered_tmos_disk_images.values():
                    if image.is_public or image.owner == tenant_id:
                        choices[i] = image
                        x.add_row([i, image.id, image.name])
                        i = i + 1
                print x
            while need_image:
                sys.stdout.write("Image? (1..%d): " % len(choices))
                choice = int(sys.stdin.readline().strip())
                if choice in range(1, len(choices) + 1):
                    policy['image'] = choices[choice].name
                    selected_image = choices[choice]
                    selected_flavor = \
                        choices[choice].properties['nova_flavor']
                    print "Setting Flavor to %s" % selected_flavor
                    need_image = False
            if need_key:
                headings = ["No.", "Key Name", "Fingerprint"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                x.add_row([0, "None", "None"])
                choices = {}
                choices[0] = 'none'
                i = 1
                for key in nova.keypairs.list():
                    choices[i] = key.id
                    x.add_row([i, key.id, key.fingerprint])
                    i = i + 1
                print x
            while need_key:
                sys.stdout.write("SSH Key? (0..%d): " % (len(choices) - 1))
                choice = int(sys.stdin.readline().strip())
                if choice in range(0, len(choices)):
                    policy['key_name'] = choices[choice]
                    need_key = False
            if need_sec_group:
                headings = ["No.", "ID", "Security Group", "Description"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                choices = {}
                i = 1
                for sg in nova.security_groups.list(
                        search_opts={'tenant_id': tenant_id}):
                    choices[i] = sg.id
                    x.add_row([i, sg.id, sg.name, sg.description])
                    i = i + 1
                print x
            while need_sec_group:
                sys.stdout.write("Security Group? (1..%d): " % len(choices))
                choice = int(sys.stdin.readline().strip())
                if choice in range(1, len(choices) + 1):
                    policy['security_group'] = choices[choice]
                    need_sec_group = False
            while need_tmos_admin_password:
                pprompt = lambda: (
                    getpass.getpass('TMOS admin password: '),
                    getpass.getpass('Retype TMOS admin password: '))
                p1, p2 = pprompt()
                while p1 != p2:
                    print('Passwords do not match. Try again')
                    p1, p2 = pprompt()
                tmos_admin_password = p1
                need_tmos_admin_password = False
            while need_tmos_root_password:
                pprompt = lambda: (
                    getpass.getpass('TMOS root password: '),
                    getpass.getpass('Retype TMOS root password: '))
                p1, p2 = pprompt()
                while p1 != p2:
                    print('Passwords do not match. Try again')
                    p1, p2 = pprompt()
                tmos_root_password = p1
                need_tmos_root_password = False
            while len(license_basekeys) < number_of_devices_needed:
                sys.stdout.write(
                    "License basekey (%d/%d): " %
                    (len(license_basekeys) + 1, number_of_devices_needed)
                )
                basekey = sys.stdin.readline().strip()
                if self._validate_basekey(basekey):
                    license_basekeys.append(str(basekey))
                else:
                    print "%s is not a valid base key" % basekey
            neutron = self._neutron.neutron_client
            networks = neutron.list_networks(tenant_id=tenant_id)['networks']
            if policy['ha_type'] == 'Standalone':
                min_networks = 2
            else:
                min_networks = 3
            if len(networks) < min_networks:
                print(
                    "Tenant %s must have at least %d networks." % (
                        policy['tenant_name'],
                        min_networks
                    ),
                    " for HA type: %s" % policy['ha_type']
                )
                print "You need at least a management network and one  network"
            if need_mgmt_net:
                headings = ["No.", "ID", "Network"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                choices = {}
                i = 1
                for net in networks:
                    if not net['id'] in assigned_networks:
                        choices[i] = net
                        x.add_row([i, net['id'], net['name']])
                        i = i + 1
                print x
            while need_mgmt_net:
                sys.stdout.write(
                    "Management Network? (1..%d): " % len(choices))
                choice = int(sys.stdin.readline().strip())
                if choice in range(1, len(choices) + 1):
                    mgmt_net = choices[choice]
                    assigned_networks.append(mgmt_net['id'])
                    need_mgmt_net = False
                    sys.stdout.write("Add a Floating IP for Access? [y/n]: ")
                    choice = sys.stdin.readline().strip()
                    if choice in ['y', 'Y', 'yes', 'YES']:
                        policy['add_floating_ip'] = 'true'
                    else:
                        policy['add_floating_ip'] = 'false'
            if need_ha_net:
                headings = ["No.", "ID", "Network"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                choices = {}
                i = 1
                for net in networks:
                    if not net['id'] in assigned_networks:
                        choices[i] = net
                        x.add_row([i, net['id'], net['name']])
                        i = i + 1
                print x
            while need_ha_net:
                sys.stdout.write("Failover Network? (1..%d): " % len(choices))
                choice = int(sys.stdin.readline().strip())
                if choice in range(1, len(choices) + 1):
                    ha_net = choices[choice]
                    assigned_networks.append(ha_net['id'])
                    need_ha_net = False
            if tenant_name == 'admin':
                sys.stdout.write(
                    "Provide VTEP endpoints for SDN tunnels? [y/n]: ")
                choice = sys.stdin.readline().strip()
                if choice in ['y', 'Y', 'yes', 'YES']:
                    need_vtep_net = True
            else:
                need_vtep_net = False
            if need_vtep_net:
                headings = ["No.", "ID", "Network"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                choices = {}
                i = 1
                for net in networks:
                    if not net['id'] in assigned_networks:
                        choices[i] = net
                        x.add_row([i, net['id'], net['name']])
                        i = i + 1
                print x
            while need_vtep_net:
                sys.stdout.write("VTEP Network? (1..%d): " % len(choices))
                choice = int(sys.stdin.readline().strip())
                if choice in range(1, len(choices) + 1):
                    vtep_net = choices[choice]
                    assigned_networks.append(vtep_net['id'])
                    need_vtep_net = False
            number_availble_vifs = MAX_VIFS - len(assigned_networks)
            for j in range(number_availble_vifs):
                # No more networks to choose
                if len(assigned_networks) == len(networks):
                    break
                # Select networks to attach
                headings = ["No.", "ID", "Network"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                choices = {}
                i = 1
                for net in networks:
                    if not net['id'] in assigned_networks:
                        choices[i] = net
                        x.add_row([i, net['id'], net['name']])
                        i = i + 1
                print x
                sys.stdout.write(
                    "Add another network? (1..%d) or N: "
                    % len(choices)
                )
                choice = sys.stdin.readline().strip()
                if choice in ['n', 'N', 'no', 'NO']:
                    break
                else:
                    choice = int(choice)
                    if choice in range(1, len(choices) + 1):
                        indexed_networks[j] = choices[choice]
                        assigned_networks.append(indexed_networks[j]['id'])

            subnets = neutron.list_subnets(tenant_id=tenant_id)['subnets']
            target_dg_subnets = []
            for subnet in subnets:
                net_id = subnet['network_id']
                if mgmt_net and net_id == mgmt_net['id']:
                    continue
                if ha_net and net_id == ha_net['id']:
                    continue
                if vtep_net and net_id == vtep_net['id']:
                    target_dg_subnets.append(
                        {'name': 'VTEP Network',
                         'gateway_ip': subnet['gateway_ip'],
                         'ip_version': subnet['ip_version']})
                elif net_id in assigned_networks:
                    target_dg_subnets.append(
                        {'name': subnet['name'],
                         'gateway_ip': subnet['gateway_ip'],
                         'ip_version': subnet['ip_version']})
                for i in indexed_networks:
                    if indexed_networks[i]['id'] == net_id:
                        indexed_networks[i]['subnet_name'] = subnet['name']

            dg_subnet = None
            need_dg = True
            if len(target_dg_subnets) == 0:
                need_dg = False
            if len(target_dg_subnets) == 1:
                dg_subnet = target_dg_subnets[0]
                need_dg = False
            if need_dg:
                headings = ["No.", "Subnet", "Gateway Address"]
                x = prettytable.PrettyTable(headings)
                for col in headings:
                    x.align[col] = 'l'
                choices = {}
                i = 1
                for dg in target_dg_subnets:
                    choices[i] = dg
                    x.add_row([i, dg['name'], dg['gateway_ip']])
                    i = i + 1
                print x
                need_dg = True
                while need_dg:
                    sys.stdout.write(
                        "Which Default Gateway? (1..%d): " % len(choices))
                    choice = int(sys.stdin.readline().strip())
                    if choice in range(1, len(choices) + 1):
                        dg_subnet = choices[choice]
                        need_dg = False

            policy['bigips'] = []
            for i in range(number_of_devices_needed):
                bigip = {}
                # add mgmt network
                bigip['network'] = {'dhcp': 'true',
                                    'management_network_id': mgmt_net['id'],
                                    'management_network_name': mgmt_net['name']
                                    }
                # set default route
                if dg_subnet:
                    dr = {}
                    if dg_subnet['ip_version'] == 4:
                        dr['destination'] = '0.0.0.0/0'
                    else:
                        dr['destination'] = '::/0'
                    dr['gateway'] = dg_subnet['gateway_ip']
                    bigip['network']['routes'] = {}
                    bigip['network']['routes'] = [dr]
                # set image metadata
                meta = {}
                meta['f5_device_group'] = policy['device_group']
                if i == 0:
                    meta['f5_device_group_primary_device'] = 'true'
                else:
                    meta['f5_device_group_primary_device'] = 'false'
                meta['f5_ha_type'] = policy['ha_type']
                meta['os_vendor'] = selected_image.properties['os_vendor']
                meta['os_version'] = selected_image.properties['os_version']
                meta['os_name'] = selected_image.properties['os_name']
                meta['os_type'] = selected_image.properties['os_type']
                bigip['flavor'] = selected_flavor
                bigip['meta'] = meta
                if 'key_name' in policy:
                    bigip['ssh_key_inject'] = 'true'
                bigip['change_passwords'] = 'true'
                bigip['admin_password'] = tmos_admin_password
                bigip['root_password'] = tmos_root_password
                basekey = license_basekeys.pop()
                bigip['license'] = {'basekey': basekey}
                bigip['network']['interfaces'] = {}
                if ha_net:
                    bigip_ha_net = {}
                    bigip_ha_net['dhcp'] = 'true'
                    bigip_ha_net['vlan_name'] = 'HA'
                    bigip_ha_net['selfip_name'] = 'HA'
                    bigip_ha_net['selfip_allow_service'] = "default"
                    bigip_ha_net['network_id'] = ha_net['id']
                    bigip_ha_net['network_name'] = ha_net['name']
                    bigip_ha_net['is_sync'] = 'true'
                    bigip_ha_net['is_failover'] = 'true'
                    bigip_ha_net['is_mirror_primary'] = 'true'
                    bigip_ha_net['is_mirror_secondary'] = 'false'
                    bigip['network']['interfaces']['1.1'] = bigip_ha_net
                if vtep_net:
                    bigip_vtep_net = {}
                    bigip_vtep_net['dhcp'] = 'true'
                    bigip_vtep_net['vlan_name'] = 'VTEP'
                    bigip_vtep_net['selfip_name'] = 'VTEP'
                    bigip_vtep_net['selfip_allow_service'] = "all"
                    bigip_vtep_net['network_id'] = vtep_net['id']
                    bigip_vtep_net['network_name'] = vtep_net['name']
                    bigip_vtep_net['is_sync'] = 'false'
                    bigip_vtep_net['is_failover'] = 'false'
                    bigip_vtep_net['is_mirror_primary'] = 'false'
                    bigip_vtep_net['is_mirror_secondary'] = 'false'
                    bigip['network']['interfaces']['1.2'] = bigip_vtep_net
                for i in indexed_networks:
                    if_index = '1.'
                    for j in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
                        if "%s%s" % (if_index, j) in \
                                bigip['network']['interfaces']:
                            continue
                        if_sub = j
                        break
                    interface = "%s%s" % (if_index, if_sub)
                    net = {}
                    net['dhcp'] = 'true'
                    net['vlan_name'] = "vlan_%s" % indexed_networks[i]['name']
                    net['vlan_name'] = net['vlan_name'][0:15]
                    if 'subnet_name' in indexed_networks[i]:
                        net['selfip_name'] = indexed_networks[i]['subnet_name']
                    else:
                        net['selfip_name'] = \
                            "selfip_%s" % indexed_networks[i]['name']
                    net['selfip_allow_service'] = "default"
                    net['network_id'] = indexed_networks[i]['id']
                    net['network_name'] = indexed_networks[i]['name']
                    net['is_sync'] = 'false'
                    net['is_failover'] = 'false'
                    net['is_mirror_primary'] = 'false'
                    net['is_mirror_secondary'] = 'false'
                    bigip['network']['interfaces'][interface] = net
                policy['bigips'].append(bigip)

            output_json = json.dumps(policies, indent=4)
            file_name = "%s_cluster_policy.json" % policy['device_group']
            sys.stdout.write("Output File [%s]: " % file_name)
            user_file_name = sys.stdin.readline().strip()
            if len(user_file_name) == 0:
                user_file_name = file_name
            if os.path.isfile(user_file_name):
                sys.stdout.write("File exists.. Overwrite? [y/n] : ")
                overwrite = strtobool(self._getch())
                if overwrite:
                    os.unlink(user_file_name)
                else:
                    for i in range(1000):
                        user_file_name = "%s._%d" % (user_file_name, i)
                        if not os.path.isfile(user_file_name):
                            break
            fd = open(user_file_name, 'w')
            fd.write(output_json)
            fd.close()
            print "Policy file %s written." % user_file_name
        except KeyboardInterrupt:
            print "\nPolicy built aborted by user input..exiting\n"
            sys.exit(0)
        except SystemExit:
            print "\nPolicy built aborted by process termination..exiting\n"
            sys.exit(0)
        sys.stdout.write("Build cluster from this policy now? [y/n]: ")
        build_dsg = strtobool(self._getch())
        if build_dsg:
            self.build_cluster(user_file_name, args)

    def build_cluster(self, policy_file, args):
        if not os.path.isfile(policy_file):
            print "can not read policy file %s " % policy_file
            sys.exit(1)
        fd = open(policy_file, 'r')
        json_data = fd.read()
        fd.close()

        bigip_image = None
        num_bigips = 0
        cluster_name = None
        ha_type = None

        admin_password = None

        mgmt_network_name = None
        ha_network_name = None

        nova = self._nova.nova_client
        neutron = self._neutron.neutron_client

        try:
            policies = json.loads(json_data)
            for dg in policies['devicegroups']:
                cluster_name = dg['device_group']
                setattr(args, 'bigip_name', "%s_" % cluster_name)
                bigip_image = dg['image']
                setattr(args, 'bigip_image', bigip_image)
                ha_type = dg['ha_type']
                setattr(args, 'ha_type', ha_type)
                setattr(args, 'security_group', dg['security_group'])
                setattr(args, 'key_name', dg['key_name'])
                setattr(args, 'no_floating_ips_file', True)
                bigips = dg['bigips']
                num_bigips = len(bigips)
                setattr(args, 'num_bigips', num_bigips)
                # add networks
                firstbigip = dg['bigips'][0]
                admin_password = firstbigip['admin_password']
                setattr(args, 'bigip_mgmt_network',
                        firstbigip['network']['management_network_id'])
                mgmt_network_name = \
                    firstbigip['network']['management_network_name']
                mgmt_network = neutron.list_networks(
                    id=firstbigip['network']['management_network_id']
                )['networks'][0]
                if mgmt_network['router:external'] or \
                   dg['add_floating_ip'] == 'false':
                    setattr(args, 'no_floating_ips', True)
                else:
                    setattr(args, 'no_floating_ips', False)
                interfaces = firstbigip['network']['interfaces']
                networks = []
                for i in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
                    interface_id = "1.%d" % i
                    if interface_id in interfaces:
                        networks.append(interfaces[interface_id]['network_id'])
                        if interfaces[interface_id]['vlan_name'] == 'HA':
                            ha_network_name = \
                                interfaces[interface_id]['network_name']
                setattr(args, 'bigip_networks', networks)
                userdatas = []
                for bigip in bigips:
                    userdata = {'bigip': bigip}
                    userdatas.append(json.dumps(userdata))
                setattr(args, 'bigip_userdata', userdatas)
                meta = firstbigip['meta']
                osmeta = {}
                for metaname in meta:
                    if metaname.startswith('os'):
                        osmeta[metaname] = meta[metaname]
                setattr(args, 'meta', osmeta)
                setattr(args, 'bigip_index', 1)
                if not dg['tenant'] == 'admin':
                    if self._creds['admin'] and \
                       self._creds['admin'].tenant_name == 'admin':
                        setattr(args, 'tenant_index', 1)
                        setattr(args, 'tenant_name', dg['tenant'])
                        setattr(args,
                                'tenane_username',
                                self._creds['admin'].username)
                        setattr(args,
                                'tenant_password',
                                self._creds['admin'].password)
                        self._creds = get_creds(args)

                if dg['tenant'] == 'admin':
                    if not self._creds['admin']:
                        msg = "ERROR: this policy was created for the admin"
                        msg += " tenant and you don't have admin credentials."
                        print msg
                        sys.exit(1)
                    admin_ve = AdminVE(self._creds['admin'], args)
                    admin_ve.set_up()
                else:
                    tenant_ve = TenantVE(self._creds, args)
                    tenant_ve.set_up()
        except Exception as e:
            print "ERROR in creating VEs %s" % e.message
            sys.exit(1)

        try:
            BIGIP_CONFIGS = []
            floatingips = neutron.list_floatingips()['floatingips']
            # add instance cluster metadata
            for i in range(1, num_bigips + 1):
                instance_name = "%s_%d" % (cluster_name, i)
                attempts = 0
                wait_for_instance = True
                while wait_for_instance and attempts < 6:
                    try:
                        server = nova.servers.list(
                            detailed=True, search_opts={'name': instance_name}
                        )[0]
                        wait_for_instance = False
                    except NotFound:
                        time.sleep(5)
                        attempts += 1
                if attempts > 5:
                    print "Could not find instance %s at 30 seconds." % \
                        instance_name
                    sys.exit(1)

                if i == 1:
                    nova.servers.set_meta_item(
                        server,
                        'f5_device_group_primary_device',
                        'true'
                    )
                nova.servers.set_meta_item(
                    server,
                    'f5_device_group',
                    cluster_name
                )
                nova.servers.set_meta_item(
                    server,
                    'f5_ha_type',
                    ha_type
                )
                # populate cluster configurations
                mgmt_ip = server.networks[mgmt_network_name][0]
                ha_ip = server.networks[ha_network_name][0]
                # find associated floating IPs
                floating_ip = mgmt_ip
                for fip in floatingips:
                    if fip['fixed_ip_address'] == mgmt_ip:
                        floating_ip = fip['floating_ip_address']
                BIGIP_CONFIG = {}
                BIGIP_CONFIG['username'] = 'admin'
                BIGIP_CONFIG['password'] = admin_password
                BIGIP_CONFIG['name'] = instance_name
                BIGIP_CONFIG['floating_ip_addr'] = floating_ip
                BIGIP_CONFIG['mgmt_addr'] = mgmt_ip
                BIGIP_CONFIG['ha_addr'] = ha_ip
                BIGIP_CONFIG['mirror_addr'] = ha_ip
                BIGIP_CONFIGS.append(BIGIP_CONFIG)
            # build cluster
            cluster = BigIpClusterGeneric(bigip_image,
                                          ha_type,
                                          num_bigips,
                                          BIGIP_CONFIGS,
                                          cluster_name)
            cluster.set_up()
        except Exception as e:
            print "ERROR in creating VE cluster %s" % e.message
            sys.exit(1)


def main(argv=None):
    if argv is None:
        argv = sys.argv

    PARSER = argparse.ArgumentParser(parents=[ADMIN_CREDS_PARSER,
                                              BASE_PARSER,
                                              CRUD_PARSER,
                                              TENANT_CREDS_PARSER])
    PARSER.add_argument(
        '-i', '--listimages',
        action="store_true",
        help='List f5 images.'
    )
    PARSER.add_argument(
        '-g', '--listinstances',
        action="store_true",
        help='List f5 guest instances.'
    )
    PARSER.add_argument(
        '-b', '--buildpolicyfile',
        action="store_true",
        help='Build a cluster policy file.'
    )
    PARSER.add_argument(
        '-p', '--clusterpolicyfile',
        default=None,
        help='Build a cluster from a policy file.'
    )
    PARSER.add_argument(
        '-j', '--json',
        action="store_true",
        help='Report with json format.'
    )
    args = PARSER.parse_args()
    clusterpolicyfile = args.clusterpolicyfile
    buildpolicyfile = False
    if args.buildpolicyfile:
        buildpolicyfile = True
    listimages = False
    if args.listimages:
        listimages = True
    listinstances = False
    if args.listinstances:
        listinstances = True
    jsonformat = False
    if args.json:
        jsonformat = True

    set_base_globals(
        openstack_api_endpoint=args.openstack_api_endpoint,
        verbose=args.verbose
    )

    set_crud_globals(
        check=args.check,
        sleep=args.sleep
    )
    creds = get_creds(args)

    manager = VECLI(creds)
    if listimages:
        manager.image_report(jsonformat)
    if listinstances:
        manager.instance_report(jsonformat)
    if buildpolicyfile:
        manager.build_policy_file(args)
        sys.exit(0)
    if clusterpolicyfile:
        manager.build_cluster(clusterpolicyfile, args)


if __name__ == "__main__":
    sys.exit(main())
