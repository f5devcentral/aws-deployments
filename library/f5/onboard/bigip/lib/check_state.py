#!/usr/bin/env python
"""Check BIG-IP State"""

import base64
import datetime
from time import sleep
from f5.bigip import bigip as bigip_icontrol

ICONTROL_USERNAME = 'admin'
ICONTROL_PASSWORD = 'admin'
ICONTROL_UNAVAILABLE_MSGS = [
    'Connection refused',
    'configuration_utility_unavailable_spinner',
    'Max retries exceeded with url',
    'No route to host',
    'Service Temporarily Unavailable']

CHECK_DEVICE_SLEEP = 10
HOTFIX_INSTALL_SLEEP = 30


def _mylog(msg):
    """Logger"""
    print "%s: %s" % (datetime.datetime.now().strftime('%b %d %H:%M:%S'), msg)


def _init_connection(bigip):
    """Initialize iControl connection"""
    if 'icontrol' not in bigip:
        if 'username' not in bigip:
            bigip['username'] = ICONTROL_USERNAME
        if 'password' not in bigip:
            bigip['password'] = ICONTROL_PASSWORD
        bigip['icontrol'] = bigip_icontrol.BigIP(
            bigip['floating_ip_addr'],
            bigip['username'],
            bigip['password'],
            timeout=5,
            address_isolation=True)


def _drop_connection(bigip):
    """Drop iControl connection"""
    if 'icontrol' in bigip:
        bigip['icontrol'] = None
        del bigip['icontrol']


def _format_icontrol_exc(exception):
    """Format iControl Exception"""
    message = exception
    for arg in exception.args:
        if any(msg in str(arg) for msg in ICONTROL_UNAVAILABLE_MSGS):
            return 'iControl is not available'
        if '' in arg:
            return '<empty iControl exception>'
    return message


class BigIpCheckState(object):

    """BigIpCheckState - Check Device State"""
    def __init__(self, bigips, product_name="BIG-IP"):
        self.product_name = product_name
        self.bigips = bigips

        for bigip_index in range(0, len(bigips)):
            bigip = self.bigips[bigip_index]
            if 'name' not in bigip:
                raise ValueError('name not supplied for item %d' % bigip_index)

            if 'floating_ip_addr' not in bigip:
                raise ValueError('floating_ip_address not supplied for %s' %
                                 bigip['name'])

    def check_device_state(self, failover_states, retry_count=40):
        """Check devices initialized and in expected failover state"""
        _mylog('Check %s(s) initialized and in expected failover state: '
               '%s.' % (self.product_name, failover_states))

        for attempt_number in range(1, retry_count + 2):
            test_passed = True

            # check all bigips
            for bigip_index in range(0, len(self.bigips)):
                bigip = self.bigips[bigip_index]
                results = {}

                try:
                    _drop_connection(bigip)
                    _init_connection(bigip)
                    results = _get_device_state(bigip, failover_states)

                # pylint: disable=broad-except
                # retry on failure
                except Exception, exception:
                    results['exception'] = _format_icontrol_exc(exception)
                # pylint: enable=broad-except

                self.log_device_state(bigip_index, results)

                if 'failover' in results and results['failover']:
                    continue
                test_passed = False

            if test_passed:
                _mylog('Test passed.  All %s(s) are in an expected '
                       'failover state.' % (self.product_name))
                return

            if attempt_number <= retry_count:
                _mylog('Test failed. Sleep %d seconds prior to retry %d of %d.'
                       % (CHECK_DEVICE_SLEEP, attempt_number, retry_count))
                sleep(CHECK_DEVICE_SLEEP)

        msg = 'Test failed.  All %s(s) are not in an expected ' \
              'failover state.' % self.product_name
        raise Exception(msg)

    def check_hotfix_install_state(self, hotfix, retry_count=90):
        """Check device hotfix installation progress"""
        _mylog('Check %s(s) hotfix installation progress volume: %s, '
               'version: %s base:%s, hotfix:%s' %
               (self.product_name,
                hotfix['install_volume'], hotfix['base_version'],
                hotfix['base_build'], hotfix['hotfix_build']))

        for attempt_number in range(1, retry_count + 2):
            test_passed = True

            # check all bigips
            for bigip_index in range(0, len(self.bigips)):
                bigip = self.bigips[bigip_index]
                results = {}

                try:
                    _drop_connection(bigip)
                    _init_connection(bigip)
                    results = _get_install_state(bigip, hotfix)

                # pylint: disable=broad-except
                # retry on failure
                except Exception, exception:
                    results['exception'] = _format_icontrol_exc(exception)
                # pylint: enable=broad-except

                self.log_install_state(bigip_index, results)

                if 'complete' in results and results['complete']:
                    continue
                test_passed = False

            if test_passed:
                _mylog('Test passed.  All %s(s) upgraded.' % self.product_name)
                return

            if attempt_number <= retry_count:
                _mylog('Test failed. Sleep %d seconds prior to retry %d of %d.'
                       % (HOTFIX_INSTALL_SLEEP, attempt_number, retry_count))
                sleep(HOTFIX_INSTALL_SLEEP)

        msg = 'Test failed.  All %s(s) were not upgraded.' % self.product_name
        raise Exception(msg)

    def log_device_state(self, bigip_index, results):
        """Log device state results"""
        msg = self.bigips[bigip_index]['name'] + ':'

        if 'exception' in results:
            msg += 'Exception - %s' % results['exception']
            _mylog(msg)
            return

        if 'license' in results:
            msg += 'Licensed'
            if 'config_loaded' in results:
                msg += ', Config:Loaded'
                if 'startup_script' in results:
                    msg += ', StartupScript:Completed'
                    if 'failover_state' in results:
                        msg += ', Failover:%s' % results['failover_state']
                    if 'failover' not in results:
                        msg += '(unexpected)'
                else:
                    msg += ', StartupScript:Running'
            else:
                msg += ', Config:NotLoaded'
        else:
            msg += 'Initializing...'
        _mylog(msg)

    def log_install_state(self, bigip_index, results):
        """Log install results"""
        msg = self.bigips[bigip_index]['name'] + ':'

        if 'exception' in results:
            msg += 'Exception - %s' % results['exception']
            _mylog(msg)
            return

        if 'base' in results:
            msg += ' BaseISO:' + results['base']
        if 'hotfix' in results:
            msg += ', HotfixISO:' + results['hotfix']
        if 'status' in results:
            msg += ', Status:' + results['status']
        else:
            msg += ' <empty results returned>'
        _mylog(msg)


def _get_device_state(bigip, failover_states):
    """Determine level of BIG-IP device initialization"""
    results = {}

    # check license
    ibig = bigip['icontrol']
    license_status = ibig.system.get_license_operational()
    if license_status is not None and license_status:
        results['license'] = True

        # check that config is loaded
        vlans = ibig.vlan.get_vlans(folder=None)
        if 'vlan.internal' in vlans or \
           'HA' in vlans:
            results['config_loaded'] = True

            if _check_startup_marker_file(bigip):
                results['startup_script'] = True

                # get failover state
                failover_state = ibig.device.get_failover_state()

                # check failover state
                results['failover_state'] = failover_state
                if failover_state in failover_states:
                    results['failover'] = True

    return results


def _check_startup_marker_file(bigip):
    """Check for startup completion marker file"""
    # check that timestamp in completion marker file has been
    # created/updated after boot.

    # marker file timestamp
    ibig = bigip['icontrol']
    try:
        file_context = ibig.system.sys_config_sync.download_file(
            '/tmp/openstack_auto_config_completed', 256, 0)
        file_update_epoch = \
            base64.standard_b64decode(file_context[0]['file_data'])
        file_update_ts = \
            datetime.datetime.utcfromtimestamp(int(file_update_epoch))
    # pylint: disable=bare-except
    # retry on failure
    except:
        # This will fail if the file doesn't exist yet - expected
        return False
    # pylint: enable=bare-except

    # current system time
    sys_time_utc = ibig.system.sys_info.get_time()
    sys_time_ts = datetime.datetime(year=sys_time_utc['year'],
                                    month=sys_time_utc['month'],
                                    day=sys_time_utc['day'],
                                    hour=sys_time_utc['hour'],
                                    minute=sys_time_utc['minute'],
                                    second=sys_time_utc['second'])

    # uptime
    sys_uptime_secs = ibig.system.sys_info.get_uptime()
    sys_uptime_td = datetime.timedelta(seconds=sys_uptime_secs)

    # derive boot time
    sys_boot_ts = sys_time_ts - sys_uptime_td

    # determine if completion marker file was updated for this boot
    if file_update_ts > sys_boot_ts:
        return True
    return False


def _get_install_state(bigip, hotfix):
    """Determine install progress"""
    results = {}
    ibig = bigip['icontrol']

    upgrade_status = ibig.system.sys_swmgmt.get_all_software_status()
    for status in upgrade_status:
        if status['installation_id']['install_volume'] == \
           hotfix['install_volume']:
            if status['build'] is None:
                return results

            if status['build'] == hotfix['base_build']:
                results['base'] = 'installing'
                results['hotfix'] = 'pending'
            else:
                results['base'] = 'installed'
                if status['build'] == hotfix['hotfix_build']:
                    if status['status'] == 'complete':
                        results['hotfix'] = 'installed'
                        results['complete'] = True
                    else:
                        results['hotfix'] = 'installing'
            results['status'] = status['status']

    return results
