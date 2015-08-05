# Copyright 2014 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from f5.common.logger import Log
from f5.common import constants as const
from f5.bigip.bigip_interfaces import icontrol_rest_folder
from f5.bigip.bigip_interfaces import icontrol_folder
from f5.bigip.bigip_interfaces import strip_domain_address
from f5.bigip.bigip_interfaces import domain_address
from f5.bigip.bigip_interfaces import log

from f5.bigip import exceptions

import json
import urllib
import netaddr


class ARP(object):

    def __init__(self, bigip):
        self.bigip = bigip
        # add iControl interfaces if they don't exist yet
        self.bigip.icontrol.add_interfaces(['Networking.ARP'])

        # iControl helper objects
        self.net_arp = self.bigip.icontrol.Networking.ARP

    '''
    @icontrol_rest_folder
    @domain_address
    @log
    def create(self, ip_address=None, mac_address=None, folder='Common'):
        payload = dict()
        payload['name'] = ip_address
        payload['partition'] = folder
        payload['ipAddress'] = ip_address
        payload['macAddress'] = mac_address
        request_url = self.icr_url + '/net/arp/'
        response = self.icr_session.post(request_url,
                              data=json.dumps(payload),
                              timeout=)
        Log.debug('ARP::create response',
                  '%s' % response.json())
        if response.status_code < 400:
            return True
        elif response.status_code == 409:
            return True
        else:
            raise exceptions.StaticARPCreationException(response.text)
    '''

    @icontrol_folder
    @domain_address
    @log
    def create(self, ip_address=None, mac_address=None, folder='Common'):
        if not self.exists(ip_address=ip_address, folder=folder):
            # ARP entries can't handle %0 on them like other
            # TMOS objects.
            ip_address = self._remove_route_domain_zero(ip_address)
            try:
                entry = \
                  self.net_arp.typefactory.create('Networking.ARP.StaticEntry')
                entry.address = ip_address
                entry.mac_address = mac_address
                self.net_arp.add_static_entry([entry])
                return True
            except Exception as e:
                Log.error('ARP', 'create exception: ' + e.message)
                raise exceptions.StaticARPCreationException(e.message)
        return False

    '''
    @icontrol_rest_folder
    @domain_address
    def delete(self, ip_address=None, folder='Common'):
        if ip_address:
            folder = str(folder).replace('/', '')
            request_url = self.bigip.icr_url + '/net/arp/'
            request_url += '~' + folder + '~' + urllib.quote(
                                  self._remove_route_domain_zero(ip_address))
            response = self.bigip.icr_session.delete(request_url,
                                            timeout=const.CONNECTION_TIMEOUT)
            if response.status_code < 400:
                return True
            elif response.status_code == 404:
                return True
            else:
                raise exceptions.StaticARPDeleteException(response.text)
                Log.error('ARP', response.text)
        return False
    '''
    @icontrol_folder
    @domain_address
    @log
    def delete(self, ip_address=None, folder='Common'):
        if self.exists(ip_address=ip_address, folder=folder):
            # ARP entries can't handle %0 on them like other
            # TMOS objects.
            ip_address = self._remove_route_domain_zero(ip_address)
            try:
                self.net_arp.delete_static_entry_v2(
                                ['/' + folder + '/' + ip_address])
                return True
            except Exception as e:
                Log.error('ARP', 'delete exception: ' + e.message)
                raise exceptions.StaticARPDeleteException(e.message)
        return False

    @icontrol_folder
    @log
    def delete_by_mac(self, mac_address=None, folder='Common'):
        if mac_address:
            arps = self.get_arps(None, folder)
            for arp in arps:
                for ip in arp:
                    if arp[ip] == mac_address:
                        self.delete(ip_address=ip, folder=folder)

    @icontrol_folder
    @log
    def delete_by_subnet(self, subnet=None, mask=None, folder='Common'):
        if subnet:
            mask_div = subnet.find('/')
            if mask_div > 0:
                try:
                    rd_div = subnet.find(':')
                    if rd_div > -1:
                        network = netaddr.IPNetwork(
                           subnet[0:mask_div][0:rd_div] + subnet[mask_div:])
                    else:
                        network = netaddr.IPNetwork(subnet)
                except Exception as e:
                    Log.error('ARP', e.message)
                    return []
            elif not mask:
                return []
            else:
                try:
                    rd_div = subnet.find(':')
                    if rd_div > -1:
                        network = netaddr.IPNetwork(
                           subnet[0:rd_div] + '/' + mask)
                    else:
                        network = netaddr.IPNetwork(subnet + '/' + mask)
                except Exception as e:
                    Log.error('ARP', e.message)
                    return []

            mac_addresses = []
            if network:
                request_url = self.bigip.icr_url + '/net/arp'
                request_filter = 'partition eq ' + folder
                request_url += '?$filter=' + request_filter
                response = self.bigip.icr_session.get(request_url,
                                           timeout=const.CONNECTION_TIMEOUT)
                Log.debug('ARP::get response', '%s' % response.json())
                if response.status_code < 400:
                    response_obj = json.loads(response.text)
                    if 'items' in response_obj:
                        for arp in response_obj['items']:
                            ad_rd_div = arp['ipAddress'].find('%')
                            address = netaddr.IPAddress(
                                        arp['ipAddress'][0:ad_rd_div])
                            if address in network:
                                mac_addresses.append(arp['macAddress'])
                                self.delete(arp['ipAddress'],
                                            folder=arp['partition'])
            return mac_addresses

    @icontrol_rest_folder
    @domain_address
    @log
    def get_arps(self, ip_address=None, folder='Common'):
        folder = str(folder).replace('/', '')
        if ip_address:
            request_url = self.bigip.icr_url + '/net/arp/'
            request_url += '~' + folder + '~' + urllib.quote(
                        self._remove_route_domain_zero(ip_address))
            response = self.bigip.icr_session.get(request_url,
                                  timeout=const.CONNECTION_TIMEOUT)
            Log.debug('ARP::get response',
                      '%s' % response.json())
            if response.status_code < 400:
                response_obj = json.loads(response.text)
                return [
                    {strip_domain_address(response_obj['name']): \
                                            response_obj['macAddress']}
                ]
            else:
                Log.error('ARP', response.text)
                raise exceptions.StaticARPQueryException(response.text)
        else:
            request_url = self.bigip.icr_url + '/net/arp'
            request_filter = 'partition eq ' + folder
            request_url += '?$filter=' + request_filter
            response = self.bigip.icr_session.get(request_url,
                                       timeout=const.CONNECTION_TIMEOUT)
            Log.debug('ARP::get response',
                      '%s' % response.json())
            if response.status_code < 400:
                response_obj = json.loads(response.text)
                if 'items' in response_obj:
                    arps = []
                    for arp in response_obj['items']:
                        arps.append(
                         {strip_domain_address(arp['name']): \
                                               arp['macAddress']}
                        )
                    return arps
            else:
                Log.error('ARP', response.text)
                raise exceptions.StaticARPQueryException(response.text)
        return []

    '''
    @icontrol_rest_folder
    def delete_all(self, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/net/arp/'
        request_url += '?$select=name,selfLink'
        request_filter = 'partition eq ' + folder
        request_url += '&$filter=' + request_filter
        response = self.bigip.icr_session.get(request_url,
                                             timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            response_obj = json.loads(response.text)
            deletions = []
            if 'items' in response_obj:
                for item in response_obj['items']:
                    if item['name'].startswith(self.OBJ_PREFIX):
                        deletions.append(self.bigip.icr_link(item['selfLink']))
            for delete in deletions:
                response = self.bigip.icr_session.delete(delete,
                                              timeout=const.CONNECTION_TIMEOUT)
                if response.status_code > 400 and \
                  (not response.status_code == 404):
                    Log.error('ARP', response.text)
                    return False
        elif response.status_code == 404:
            return True
        else:
            Log.error('ARP', response.text)
            exceptions.StaticARPDeleteException(response.text)
     '''

    @icontrol_folder
    @log
    def delete_all(self, folder='Common'):
        try:
            self.net_arp.delete_all_static_entries()
        except Exception as e:
            Log.error('ARP', 'delete exception: ' + e.message)
            raise exceptions.StaticARPDeleteException(e.message)

    '''
    @icontrol_rest_folder
    @domain_address
    def exists(self, ip_address=None, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/net/arp/'
        request_url += '~' + folder + '~' + urllib.quote(
                        self._remove_route_domain_zero(ip_address))
        response = self.bigip.icr_session.get(request_url,
                                  timeout=const.CONNECTION_TIMEOUT)
        Log.debug('ARP::exists response',
                      '%s' % response.text)
        if response.status_code < 400:
            return True
        return False
    '''

    @icontrol_folder
    @domain_address
    @log
    def exists(self, ip_address=None, folder='Common'):
        # ARP entries can't handle %0 on them like other
        # TMOS objects.
        ip_address = self._remove_route_domain_zero(ip_address)
        if '/' + folder + '/' + ip_address in \
                  self.net_arp.get_static_entry_list():
            return True
        else:
            return False

    def _remove_route_domain_zero(self, ip_address):
        decorator_index = ip_address.find('%0')
        if decorator_index > 0:
            ip_address = ip_address[:decorator_index]
        return ip_address
