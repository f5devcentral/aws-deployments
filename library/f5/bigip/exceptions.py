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
"""Exceptions"""


class MinorVersionValidateFailed(Exception):
    """MinorVersionValidateFailed"""
    pass


class MajorVersionValidateFailed(Exception):
    """MajorVersionValidateFailed"""
    pass


class ProvisioningExtraMBValidateFailed(Exception):
    """ProvisioningExtraMBValidateFailed"""
    pass


class BigIPDeviceLockAcquireFailed(Exception):
    """BigIPDeviceLockAcquireFailed"""
    pass


class BigIPClusterInvalidHA(Exception):
    """BigIPClusterInvalidHA"""
    pass


class BigIPClusterSyncFailure(Exception):
    """BigIPClusterSyncFailure"""
    pass


class BigIPClusterPeerAddFailure(Exception):
    """BigIPClusterPeerAddFailure"""
    pass


class BigIPClusterConfigSaveFailure(Exception):
    """BigIPClusterConfigSaveFailure"""
    pass


class UnknownMonitorType(Exception):
    """UnknownMonitorType"""
    pass


class MissingVTEPAddress(Exception):
    """MissingVTEPAddress"""
    pass


class MissingNetwork(Exception):
    """MissingNetwork"""
    pass


class InvalidNetworkType(Exception):
    """InvalidNetworkType"""
    pass


class StaticARPCreationException(Exception):
    """StaticARPCreationException"""
    pass


class StaticARPQueryException(Exception):
    """StaticARPQueryException"""
    pass


class StaticARPDeleteException(Exception):
    """StaticARPDeleteException"""
    pass


class ClusterCreationException(Exception):
    """ClusterCreationException"""
    pass


class ClusterUpdateException(Exception):
    """ClusterUpdateException"""
    pass


class ClusterQueryException(Exception):
    """ClusterQueryException"""
    pass


class ClusterDeleteException(Exception):
    """ClusterDeleteException"""
    pass


class DeviceCreationException(Exception):
    """DeviceCreationException"""
    pass


class DeviceUpdateException(Exception):
    """DeviceUpdateException"""
    pass


class DeviceQueryException(Exception):
    """DeviceQueryException"""
    pass


class DeviceDeleteException(Exception):
    """DeviceDeleteException"""
    pass


class InterfaceQueryException(Exception):
    """InterfaceQueryException"""
    pass


class IAppCreationException(Exception):
    """IAppCreationException"""
    pass


class IAppQueryException(Exception):
    """IAppQueryException"""
    pass


class IAppUpdateException(Exception):
    """IAppUpdateException"""
    pass


class IAppDeleteException(Exception):
    """IAppDeleteException"""
    pass


class L2GRETunnelCreationException(Exception):
    """L2GRETunnelCreationException"""
    pass


class L2GRETunnelQueryException(Exception):
    """L2GRETunnelQueryException"""
    pass


class L2GRETunnelUpdateException(Exception):
    """L2GRETunnelUpdateException"""
    pass


class L2GRETunnelDeleteException(Exception):
    """L2GRETunnelDeleteException"""
    pass


class MonitorCreationException(Exception):
    """MonitorCreationException"""
    pass


class MonitorQueryException(Exception):
    """MonitorQueryException"""
    pass


class MonitorUpdateException(Exception):
    """MonitorUpdateException"""
    pass


class MonitorDeleteException(Exception):
    """MonitorDeleteException"""
    pass


class NATCreationException(Exception):
    """NATCreationException"""
    pass


class NATQueryException(Exception):
    """NATQueryException"""
    pass


class NATUpdateException(Exception):
    """NATUpdateException"""
    pass


class NATDeleteException(Exception):
    """NATDeleteException"""
    pass


class PoolCreationException(Exception):
    """PoolCreationException"""
    pass


class PoolQueryException(Exception):
    """PoolQueryException"""
    pass


class PoolUpdateException(Exception):
    """PoolUpdateException"""
    pass


class PoolDeleteException(Exception):
    """PoolDeleteException"""
    pass


class RouteCreationException(Exception):
    """RouteCreationException"""
    pass


class RouteQueryException(Exception):
    """RouteQueryException"""
    pass


class RouteUpdateException(Exception):
    """RouteUpdateException"""
    pass


class RouteDeleteException(Exception):
    """RouteDeleteException"""
    pass


class RuleCreationException(Exception):
    """RuleCreationException"""
    pass


class RuleQueryException(Exception):
    """RuleQueryException"""
    pass


class RuleUpdateException(Exception):
    """RuleUpdateException"""
    pass


class RuleDeleteException(Exception):
    """RuleDeleteException"""
    pass


class SelfIPCreationException(Exception):
    """SelfIPCreationException"""
    pass


class SelfIPQueryException(Exception):
    """SelfIPQueryException"""
    pass


class SelfIPUpdateException(Exception):
    """SelfIPUpdateException"""
    pass


class SelfIPDeleteException(Exception):
    """SelfIPDeleteException"""
    pass


class SNATCreationException(Exception):
    """SNATCreationException"""
    pass


class SNATQueryException(Exception):
    """SNATQueryException"""
    pass


class SNATUpdateException(Exception):
    """SNATUpdateException"""
    pass


class SNATDeleteException(Exception):
    """SNATDeleteException"""
    pass


class SystemCreationException(Exception):
    """SystemCreationException"""
    pass


class SystemQueryException(Exception):
    """SystemQueryException"""
    pass


class SystemUpdateException(Exception):
    """SystemUpdateException"""
    pass


class SystemDeleteException(Exception):
    """SystemDeleteException"""
    pass


class VirtualServerCreationException(Exception):
    """VirtualServerCreationException"""
    pass


class VirtualServerQueryException(Exception):
    """VirtualServerQueryException"""
    pass


class VirtualServerUpdateException(Exception):
    """VirtualServerUpdateException"""
    pass


class VirtualServerDeleteException(Exception):
    """VirtualServerDeleteException"""
    pass


class VLANCreationException(Exception):
    """VLANCreationException"""
    pass


class VLANQueryException(Exception):
    """VLANQueryException"""
    pass


class VLANUpdateException(Exception):
    """VLANUpdateException"""
    pass


class VLANDeleteException(Exception):
    """VLANDeleteException"""
    pass


class VXLANCreationException(Exception):
    """VXLANCreationException"""
    pass


class VXLANQueryException(Exception):
    """VXLANQueryException"""
    pass


class VXLANUpdateException(Exception):
    """VXLANUpdateException"""
    pass


class VXLANDeleteException(Exception):
    """VXLANDeleteException"""
    pass
