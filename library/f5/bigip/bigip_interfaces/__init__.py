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

import netaddr
import os
import logging

OBJ_PREFIX = 'uuid_'

LOG = logging.getLogger(__name__)


def prefixed(name):
    if not name.startswith(OBJ_PREFIX):
        name = OBJ_PREFIX + name
    return name


def icontrol_folder(method):
    """
    Returns the iControl folder + object name if
    a kwarg name is 'name' or else ends in '_name'.

    The folder and the name will be prefixed with the global
    prefix OBJ_PREFIX. If preserve_vlan_name=True is an argument,
    then the 'vlan_name' argument will not be prefixed but the
    other matching arguments will.

    It also sets the iControl active folder to folder kwarg
    assuring get_list returns just the appopriate objects
    for the specific administrative partition. It does this
    for kwarg named 'name', ends in '_name', or 'named_address'.

    If the value in the name already includes '/Common/' the
    decoration honors that full path.
    """
    def wrapper(*args, **kwargs):
        instance = args[0]
        preserve_vlan_name = False
        if 'preserve_vlan_name' in kwargs:
            preserve_vlan_name = kwargs['preserve_vlan_name']
        if 'folder' in kwargs and kwargs['folder']:
            if kwargs['folder'].find('~') > -1:
                kwargs['folder'] = kwargs['folder'].replace('~', '/')
            kwargs['folder'] = os.path.basename(kwargs['folder'])
            if not kwargs['folder'] == 'Common':
                kwargs['folder'] = prefixed(kwargs['folder'])
            if 'name' in kwargs and kwargs['name']:
                if isinstance(kwargs['name'], basestring):
                    if kwargs['name'].find('~') > -1:
                        kwargs['name'] = kwargs['name'].replace('~', '/')
                    if kwargs['name'].startswith('/Common/'):
                        kwargs['name'] = os.path.basename(kwargs['name'])
                        kwargs['name'] = prefixed(kwargs['name'])
                        kwargs['name'] = instance.bigip.set_folder(
                                                            kwargs['name'],
                                                            'Common')
                    else:
                        kwargs['name'] = os.path.basename(kwargs['name'])
                        kwargs['name'] = prefixed(kwargs['name'])
                        kwargs['name'] = instance.bigip.set_folder(
                                                            kwargs['name'],
                                                            kwargs['folder'])
            if 'named_address' in kwargs and kwargs['named_address']:
                if isinstance(kwargs['name'], basestring):
                    if kwargs['named_address'].find('~') > -1:
                        kwargs['named_address'] = \
                                         kwargs['named_address'].replace('~',
                                                                         '/')
                    if kwargs['named_address'].startswith('/Common/'):
                        kwargs['named_address'] = \
                            os.path.basename(kwargs['named_address'])
                        kwargs['named_address'] = \
                            instance.bigip.set_folder(kwargs['named_address'],
                                                      'Common')
                    else:
                        kwargs['named_address'] = \
                            os.path.basename(kwargs['named_address'])
                        kwargs['named_address'] = \
                            instance.bigip.set_folder(kwargs['named_address'],
                                                      kwargs['folder'])
            for name in kwargs:
                if name.find('_folder') > 0 and kwargs[name]:
                    if kwargs[name].find('~') > -1:
                        kwargs[name] = kwargs[name].replace('~', '/')
                    kwargs[name] = os.path.basename(kwargs[name])
                    if not kwargs[name] == 'Common':
                        kwargs[name] = prefixed(kwargs[name])
                if name.find('_name') > 0 and kwargs[name]:
                    if isinstance(kwargs['name'], basestring):
                        if kwargs[name].find('~') > -1:
                            kwargs[name] = kwargs[name].replace('~', '/')
                        if kwargs[name].startswith('/Common/'):
                            kwargs[name] = os.path.basename(kwargs[name])
                            if name != 'vlan_name' or not preserve_vlan_name:
                                kwargs[name] = prefixed(kwargs[name])
                            kwargs[name] = instance.bigip.set_folder(
                                                                kwargs[name],
                                                                'Common')
                        else:
                            name_prefix = name[0:name.index('_name')]
                            specific_folder_name = name_prefix + "_folder"
                            folder = kwargs['folder']
                            if specific_folder_name in kwargs:
                                folder = kwargs[specific_folder_name]
                            kwargs[name] = os.path.basename(kwargs[name])
                            if name != 'vlan_name' or not preserve_vlan_name:
                                kwargs[name] = prefixed(kwargs[name])
                            kwargs[name] = instance.bigip.set_folder(
                                                                kwargs[name],
                                                                folder)
            instance.bigip.set_folder(None, kwargs['folder'])
        return method(*args, **kwargs)
    return wrapper


def icontrol_rest_folder(method):
    """
    Returns iControl REST folder + object name if
    a kwarg name is 'name' or else ends in '_name'.

    The folder and the name will be prefixed with the global
    prefix OBJ_PREFIX.
    """
    def wrapper(*args, **kwargs):
        preserve_vlan_name = False
        if 'preserve_vlan_name' in kwargs:
            preserve_vlan_name = kwargs['preserve_vlan_name']
        if 'folder' in kwargs and kwargs['folder']:
            if not kwargs['folder'] == '/':
                if kwargs['folder'].find('Common') < 0:
                    if kwargs['folder'].find('~') > -1:
                        kwargs['folder'] = kwargs['folder'].replace('~', '/')
                        kwargs['folder'] = os.path.basename(kwargs['folder'])
                    if kwargs['folder'].find('/') > -1:
                        kwargs['folder'] = os.path.basename(kwargs['folder'])
                    kwargs['folder'] = prefixed(kwargs['folder'])
        if 'name' in kwargs and kwargs['name']:
            if isinstance(kwargs['name'], basestring):
                if kwargs['name'].find('~') > -1:
                    kwargs['name'] = kwargs['name'].replace('~', '/')
                    kwargs['name'] = os.path.basename(kwargs['name'])
                if kwargs['name'].find('/') > -1:
                    kwargs['name'] = os.path.basename(kwargs['name'])
                kwargs['name'] = prefixed(kwargs['name'])
        for name in kwargs:
            if name.find('_folder') > 0 and kwargs[name]:
                if kwargs[name].find('~') > -1:
                    kwargs[name] = kwargs[name].replace('~', '/')
                kwargs[name] = os.path.basename(kwargs[name])
                if not kwargs[name] == 'Common':
                    kwargs[name] = prefixed(kwargs[name])
            if name.find('_name') > 0 and kwargs[name]:
                if isinstance(kwargs[name], basestring):
                    if kwargs[name].find('~') > -1:
                        kwargs[name] = kwargs[name].replace('~', '/')
                        kwargs[name] = os.path.basename(kwargs[name])
                    if kwargs[name].find('/') > -1:
                        kwargs[name] = os.path.basename(kwargs[name])
                    if name != 'vlan_name' or not preserve_vlan_name:
                        kwargs[name] = prefixed(kwargs[name])
        return method(*args, **kwargs)
    return wrapper


def domain_address(method):
    """
    Validates the format of IPv4 or IPv6 address values and
    puts the right route domain decoration on address
    values with kwargs named 'ip_address' or else ending
    in '_ip_address'. Handles single values or a list.

    Netmask formats are validated too for any kwarg with name
    including 'mask'. These can be single values or a list.

    It will discover the route domain ID based upon kwarg values
    with the name 'folder' or else with the name ending '_folder'
    where the prefix to the '_folder' name matches the characters
    in front of the '_ip_address' of the address name.

    It is assuming that there is only one route domain for the
    discovered folder.

    The route domain decoration is by-passed in one of two
    conditions:

    1) the bigip object route_domain_required attribute is False
    2) the address value passed in has a '%' in it already

    IP address validation always takes place.

    This decorator assume the requirement for an object name
    prefix for folders.  It will prepend the OBJ_PREFIX to
    all folders.
    """
    def wrapper(*args, **kwargs):
        instance = args[0]
        if not instance.bigip.route_domain_required:
            return method(*args, **kwargs)

        folder = 'Common'
        # discover the folder add global prefix
        if 'folder' in kwargs and kwargs['folder']:
            folder = os.path.basename(kwargs['folder'])
            if not folder == 'Common':
                folder = prefixed(folder)
        # iterate through kwargs
        for name in kwargs:
            # validate netmask IP formatting
            if name.find('mask') > -1:
                if isinstance(kwargs[name], list):
                    for mask in kwargs[name]:
                        netaddr.IPAddress(mask)
                else:
                    if kwargs[name]:
                        netaddr.IPAddress(kwargs[name])
            # find any argument ending in ip_address
            if name.find('ip_address') > -1:
                # if it has a value process the route domain ID
                if kwargs[name]:

                    # if this name has _ip_address in it, check
                    # for _folder argument with the same prefix.
                    # if found use that argument to overwrite
                    # the folder argument
                    if name.find('_ip_address') > -1:
                        name_prefix = name[0:name.index('_ip_address')]
                        specific_folder_name = name_prefix + "_folder"
                        # do we also find another kwargs with a
                        # folder name for this _ip_address argument
                        if specific_folder_name in kwargs:
                            folder = kwargs[specific_folder_name]

                    # handle if they passed in a list of value
                    if isinstance(kwargs[name], list):
                        return_list = []
                        for address in kwargs[name]:
                            decorator_index = address.find('%')
                            if decorator_index < 0:
                                # validate address format
                                netaddr.IPAddress(address)
                                if instance.bigip.route_domain_required:
                                    # discover route domain
                                    rid = \
                                      instance.bigip.get_domain_index(folder)
                                    # decorate address
                                    if rid > 0:
                                        address = address + "%" + str(rid)
                            else:
                                # validate_address format
                                netaddr.IPAddress(
                                               address[:decorator_index])
                            return_list.append(address)
                        # overwrite argument value with now decorated
                        # values list
                        kwargs[name] = return_list
                    else:
                        # handle an individual value
                        decorator_index = kwargs[name].find('%')
                        if decorator_index < 0:
                            # validate address
                            netaddr.IPAddress(kwargs[name])
                            if instance.bigip.route_domain_required:
                                # discover route domain
                                rid = instance.bigip.get_domain_index(folder)
                                # decorate address
                                if rid > 0:
                                    kwargs[name] = kwargs[name] + \
                                                        "%" + str(rid)
                        else:
                            # validate address
                            address = kwargs[name][:decorator_index]
                            netaddr.IPAddress(address)
        return method(*args, **kwargs)
    return wrapper


def decorate_name(name=None, folder='Common', use_prefix=True):
    folder = os.path.basename(folder)
    if not folder == 'Common':
        folder = prefixed(folder)
    if name.startswith('/Common/'):
        name = os.path.basename(name)
        if use_prefix:
            name = prefixed(name)
        name = '/Common/' + name
    else:
        name = os.path.basename(name)
        if use_prefix:
            name = prefixed(name)
        name = '/' + folder + '/' + name
    return name


def strip_folder_and_prefix(path):
    if isinstance(path, list):
        for i in range(len(path)):
            if path[i].find('~') > -1:
                path[i] = path[i].replace('~', '/')
            if path[i].startswith('/Common'):
                path[i] = path[i].replace(OBJ_PREFIX, '')
            else:
                path[i] = \
                  os.path.basename(str(path[i])).replace(OBJ_PREFIX, '')
        return path
    else:
        if path.find('~') > -1:
            path = path.replace('~', '/')
        if path.startswith('/Common'):
            return str(path).replace(OBJ_PREFIX, '')
        else:
            return os.path.basename(str(path)).replace(OBJ_PREFIX, '')


def strip_domain_address(ip_address):
    mask_index = ip_address.find('/')
    if mask_index > 0:
        return ip_address[:mask_index].split('%')[0] + ip_address[mask_index:]
    else:
        return ip_address.split('%')[0]


def log(method):
    """Decorator helping to log method calls."""
    def wrapper(*args, **kwargs):
        instance = args[0]
        LOG.debug('%s::%s called with args: %s kwargs: %s' % (
                                            instance.__class__.__name__,
                                            method.__name__,
                                            args[1:],
                                            kwargs
                                           ))
        return method(*args, **kwargs)
    return wrapper
