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
from f5.bigip.bigip_interfaces import domain_address
from f5.bigip.bigip_interfaces import icontrol_rest_folder
from f5.bigip.bigip_interfaces import strip_folder_and_prefix
from f5.bigip import exceptions
from f5.bigip.bigip_interfaces import log

import json
import os


class SNAT(object):
    def __init__(self, bigip):
        self.bigip = bigip

    @icontrol_rest_folder
    @domain_address
    @log
    def create(self, name=None, ip_address=None,
               traffic_group=None, snat_pool_name=None,
               folder='Common', snat_pool_folder=None):
        if not traffic_group:
            traffic_group = const.SHARED_CONFIG_DEFAULT_TRAFFIC_GROUP
        if name:
            folder = str(folder).replace('/', '')
            self.bigip.system.set_rest_folder(folder)
            # create snat address
            payload = dict()
            payload['name'] = name
            payload['partition'] = folder
            payload['address'] = ip_address
            payload['trafficGroup'] = traffic_group
            request_url = self.bigip.icr_url + '/ltm/snat-translation'
            response = self.bigip.icr_session.post(request_url,
                                             data=json.dumps(payload),
                                             timeout=const.CONNECTION_TIMEOUT)
            if not (response.status_code < 400 or \
                    response.status_code == 409):
                Log.error('snat-translation', response.text)
                raise exceptions.SNATCreationException(response.text)

            if snat_pool_name:
                if not snat_pool_folder:
                    snat_pool_folder = folder
                # create snat pool with member
                sa_path = '/' + folder + '/' + name
                payload = dict()
                payload['name'] = snat_pool_name
                payload['partition'] = snat_pool_folder
                payload['members'] = [sa_path]
                request_url = self.bigip.icr_url + '/ltm/snatpool'
                response = self.bigip.icr_session.post(request_url,
                                        data=json.dumps(payload),
                                        timeout=const.CONNECTION_TIMEOUT)
                if response.status_code == 409:
                    # get existing members
                    request_url += '/~' + snat_pool_folder
                    request_url += '~' + snat_pool_name
                    request_url += '?$select=members'
                    response = self.bigip.icr_session.get(request_url,
                                        timeout=const.CONNECTION_TIMEOUT)
                    if response.status_code < 400:
                        response_obj = json.loads(response.text)
                        if 'members' in response_obj:
                            if not sa_path in response_obj['members']:
                                members = response_obj['members']
                                members.append(sa_path)
                            else:
                                return True
                        else:
                            members = [sa_path]
                    elif response.status_code != 404:
                        Log.error('snatpool', response.text)
                        raise exceptions.SNATQueryException(response.text)
                    payload = dict()
                    payload['members'] = members
                    request_url = self.bigip.icr_url + '/ltm/snatpool'
                    request_url += '/~' + snat_pool_folder
                    request_url += '~' + snat_pool_name
                    response = self.bigip.icr_session.put(request_url,
                                           data=json.dumps(payload),
                                           timeout=const.CONNECTION_TIMEOUT)
                elif response.status_code < 400:
                    return True
                else:
                    Log.error('snatpool', response.text)
                    raise exceptions.SNATCreationException(response.text)
        return False

    @icontrol_rest_folder
    @log
    def delete(self, name=None, folder='Common', snat_pool_folder=None):
        if name:
            folder = str(folder).replace('/', '')
            request_url = self.bigip.icr_url + '/ltm/snat-translation/'
            request_url += '~' + folder + '~' + name
            response = self.bigip.icr_session.delete(request_url,
                                  timeout=const.CONNECTION_TIMEOUT)
            if response.status_code < 400:
                return True
            elif response.status_code == 400 and \
                (response.text.find('is still referenced') > 0):
                # what SNAT pool is referencing this SNAT address
                if not snat_pool_folder:
                    snat_pool_folder = folder
                pool_req_url = self.bigip.icr_url + '/ltm/snatpool'
                request_filter = 'partition eq ' + snat_pool_folder
                response = self.bigip.icr_session.get(
                                pool_req_url + '?$filter=' + request_filter,
                                timeout=const.CONNECTION_TIMEOUT)
                if response.status_code < 400:
                    response_obj = json.loads(response.text)
                    if 'items' in response_obj:
                        for snatpool in response_obj['items']:
                            if 'members' in snatpool:
                                snat_path = '/' + folder + '/' + name
                                if snat_path in snatpool['members']:
                                    if len(snatpool['members']) == 1:
                                        # if this is the last SNAT address
                                        # in this SNAT pool delete
                                        #the SNAT pool
                                        response = \
                                          self.bigip.icr_session.delete(
                                            self.bigip.icr_link(
                                                        snatpool['selfLink']),
                                            timeout=const.CONNECTION_TIMEOUT)
                                        if response.status_code < 400:
                                            return True
                                        elif response.status_code != 404:
                                            Log.error('snat-translation',
                                                      response.text)
                                            raise \
                                                exceptions.SNATDeleteException(
                                                                 response.text)
                                    else:
                                        if self.remove_from_pool(
                                                name=snatpool['name'],
                                                member_name=name,
                                                folder=snat_pool_folder):
                                        # now try to delete it again
                                            response = \
                                              self.bigip.icr_session.delete(
                                             request_url,
                                             timeout=const.CONNECTION_TIMEOUT)
                                            if response.status_code < 400:
                                                return True
                                            elif response.status_code == 404:
                                                return True
                                            else:
                                                Log.error('snat-translation',
                                                          response.text)
                                                raise \
                                exceptions.SNATDeleteException(response.text)
            elif response.status_code != 404:
                Log.error('snat-translation', response.text)
                raise exceptions.SNATDeleteException(response.text)
            else:
                return True
        return False

    @icontrol_rest_folder
    @log
    def delete_all(self, folder='Common'):
        folder = str(folder).replace('/', '')
        self.delete_all_snatpools(folder)
        request_url = self.bigip.icr_url + '/ltm/snat-translation/'
        request_url += '?$select=name,selfLink'
        request_filter = 'partition eq ' + folder
        request_url += '&$filter=' + request_filter
        response = self.bigip.icr_session.get(request_url,
                                            timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            response_obj = json.loads(response.text)
            if 'items' in response_obj:
                for item in response_obj['items']:
                    if item['name'].startswith(self.OBJ_PREFIX):
                        response = self.bigip.icr_session.delete(
                                       self.bigip.icr_link(item['selfLink']),
                                       timeout=const.CONNECTION_TIMEOUT)
                        if response.status_code > 400 and \
                           response.status_code != 404:
                            Log.error('snat-translation', response.text)
                            raise exceptions.SNATDeleteException(response.text)
            return True
        elif response.status_code != 404:
            Log.error('snat-translation', response.text)
            raise exceptions.SNATQueryException(response.text)
        return False

    @icontrol_rest_folder
    @log
    def delete_snatpool(self, name=None, folder='Common'):
        if name:
            folder = str(folder).replace('/', '')
            request_url = self.bigip.icr_url + '/ltm/snatpool/'
            request_url += '?$select=name,selfLink'
            request_filter = 'partition eq ' + folder
            request_url += '&$filter=' + request_filter
            response = self.bigip.icr_session.get(request_url,
                                timeout=const.CONNECTION_TIMEOUT)
            if response.status_code < 400:
                response_obj = json.loads(response.text)
                if 'items' in response_obj:
                    for item in response_obj['items']:
                        if item['name'] == name:
                            response = self.bigip.icr_session.delete(
                                        self.bigip.icr_link(item['selfLink']),
                                        timeout=const.CONNECTION_TIMEOUT)
                            if response.status_code > 400 and \
                               response.status_code != 404:
                                Log.error('snatpool', response.text)
                                raise exceptions.SNATDeleteException(
                                                                response.text)
                return True
            elif response.status_code != 404:
                Log.error('snatpool', response.text)
                raise exceptions.SNATQueryException(response.text)
        return False

    @icontrol_rest_folder
    @log
    def delete_all_snatpools(self, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/ltm/snatpool/'
        request_url += '?$select=name,selfLink'
        request_filter = 'partition eq ' + folder
        request_url += '&$filter=' + request_filter
        response = self.bigip.icr_session.get(request_url,
                                            timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            response_obj = json.loads(response.text)
            if 'items' in response_obj:
                for item in response_obj['items']:
                    if item['name'].startswith(self.OBJ_PREFIX):
                        response = self.bigip.icr_session.delete(
                                       self.bigip.icr_link(item['selfLink']),
                                       timeout=const.CONNECTION_TIMEOUT)
                        if response.status_code > 400 and \
                           response.status_code != 404:
                            Log.error('snatpool', response.text)
                            raise exceptions.SNATDeleteException(response.text)
            return True
        elif response.status_code != 404:
            Log.error('snatpool', response.text)
            raise exceptions.SNATQueryException(response.text)
        return False

    @icontrol_rest_folder
    @log
    def get_snataddresses(self, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/ltm/snat-translation/'
        request_url += '?$select=name'
        if folder:
            request_filter = 'partition eq ' + folder
            request_url += '&$filter=' + request_filter
        response = self.bigip.icr_session.get(request_url,
                                          timeout=const.CONNECTION_TIMEOUT)
        return_list = []
        if response.status_code < 400:
            return_obj = json.loads(response.text)
            if 'items' in return_obj:
                for sa in return_obj['items']:
                    return_list.append(strip_folder_and_prefix(sa['name']))
        elif response.status_code != 404:
            Log.error('snat-translation', response.text)
            raise exceptions.SNATQueryException(response.text)
        return return_list

    @icontrol_rest_folder
    @log
    def get_snatpool_members(self, name=None, folder='Common'):
        if name:
            folder = str(folder).replace('/', '')
            request_url = self.bigip.icr_url + '/ltm/snatpool/'
            request_url += '~' + folder + '~' + name
            request_url += '/?$select=members'
            response = self.bigip.icr_session.get(request_url,
                                     timeout=const.CONNECTION_TIMEOUT)
            return_list = []
            if response.status_code < 400:
                return_obj = json.loads(response.text)
                if 'members' in return_obj:
                    for sa in return_obj['members']:
                        return_list.append(strip_folder_and_prefix(sa))
            elif response.status_code != 404:
                Log.error('snatpool', response.text)
                raise exceptions.SNATQueryException(response.text)
            return return_list
        return None

    @icontrol_rest_folder
    @log
    def create_pool(self, name=None, member_name=None, folder='Common'):
        if name:
            folder = str(folder).replace('/', '')
            payload = dict()
            payload['name'] = name
            payload['partition'] = folder
            payload['members'] = [member_name]
            request_url = self.bigip.icr_url + '/ltm/snatpool'
            response = self.bigip.icr_session.post(request_url,
                                   data=json.dumps(payload),
                                   timeout=const.CONNECTION_TIMEOUT)
            if response.status_code < 400 or \
                    response.status_code == 409:
                return True
            else:
                Log.error('snatpool', response.text)
                raise exceptions.SNATCreationException(response.text)
        return False

    @icontrol_rest_folder
    @log
    def add_to_pool(self, name=None, member_name=None, folder='Common'):
        folder = str(folder).replace('/', '')
        sa_path = '/' + folder + '/' + member_name
        request_url = self.bigip.icr_url + '/ltm/snatpool'
        request_url += '/~' + folder + '~' + name
        request_url += '?$select=members'
        response = self.bigip.icr_session.get(request_url,
                                      timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            response_obj = json.loads(response.text)
            if 'members' in response_obj:
                if not sa_path in response_obj['members']:
                    members = response['members']
                    members.append(sa_path)
                else:
                    return True
            else:
                members = [sa_path]
        else:
            Log.error('snatpool', response.text)
            raise exceptions.SNATQueryException(response.text)
        payload = dict()
        payload['members'] = members
        request_url += '/~' + folder + '~' + name
        response = self.bigip.icr_session.put(request_url,
                                         data=json.dumps(payload),
                                         timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            return True
        else:
            Log.error('snatpool', response.text)
            raise exceptions.SNATUpdateException(response.text)
        return False

    @icontrol_rest_folder
    @log
    def remove_from_pool(self, name=None, member_name=None, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/ltm/snatpool'
        request_url += '/~' + folder + '~' + name
        request_url += '?$select=members'
        response = self.bigip.icr_session.get(request_url,
                                        timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            response_obj = json.loads(response.text)
            sa_to_remove = None
            for member in response_obj['members']:
                member_base_name = os.path.basename(member)
                if member_base_name == member_name:
                    sa_to_remove = member
            if not sa_to_remove:
                return True
            else:
                members = response_obj['members']
                if len(members) == 1:
                    request_url = self.bigip.icr_url + '/ltm/snatpool'
                    request_url += '/~' + folder + '~' + name
                    response = self.bigip.icr_session.delete(request_url,
                                          timeout=const.CONNECTION_TIMEOUT)
                    if response.status_code:
                        return True
                    else:
                        Log.error('snatpool', response.text)
                        raise exceptions.SNATDeleteException(response.text)
                else:
                    members.remove(sa_to_remove)
                    payload = dict()
                    payload['members'] = members
                    request_url = self.bigip.icr_url
                    request_url += '/ltm/snatpool'
                    request_url += '/~' + folder + '~' + name
                    response = self.bigip.icr_session.put(request_url,
                                          data=json.dumps(payload),
                                          timeout=const.CONNECTION_TIMEOUT)
                    if response.status_code < 400:
                        return True
                    else:
                        Log.error('snatpool', response.text)
                        raise exceptions.SNATUpdateException(response.text)
        else:
            Log.error('snatpool', response.text)
            raise exceptions.SNATQueryException(response.text)
        return False

    @icontrol_rest_folder
    @log
    def pool_exists(self, name=None, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/ltm/snatpool/'
        request_url += '~' + folder + '~' + name
        request_url += '?$select=name'
        response = self.bigip.icr_session.get(request_url,
                             timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            return True
        elif response.status_code == 404:
            return False
        else:
            raise exceptions.SNATQueryException(response.text)

    @icontrol_rest_folder
    @log
    def get_snatpools(self, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/ltm/snatpool/'
        request_url += '?$select=name'
        if folder:
            request_filter = 'partition eq ' + folder
            request_url += '&$filter=' + request_filter
        response = self.bigip.icr_session.get(request_url,
                                            timeout=const.CONNECTION_TIMEOUT)
        return_list = []
        if response.status_code < 400:
            return_obj = json.loads(response.text)
            if 'items' in return_obj:
                for pool in return_obj['items']:
                    return_list.append(strip_folder_and_prefix(pool['name']))
        elif response.status_code != 404:
            Log.error('snatpool', response.text)
            raise exceptions.SNATQueryException(response.text)
        return return_list

    @icontrol_rest_folder
    @log
    def exists(self, name=None, folder='Common'):
        folder = str(folder).replace('/', '')
        request_url = self.bigip.icr_url + '/ltm/snat-translation/'
        request_url += '~' + folder + '~' + name
        request_url += '?$select=name'
        response = self.bigip.icr_session.get(request_url,
                                        timeout=const.CONNECTION_TIMEOUT)
        if response.status_code < 400:
            return True
        elif response.status_code != 404:
            Log.error('snat-translation', response.text)
            raise exceptions.SNATQueryException(response.text)
        else:
            return False
