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

from f5.common import constants as const
from f5.bigip.bigip_interfaces import log

import time


class Stat(object):
    def __init__(self, bigip):
        self.bigip = bigip

        # add iControl interfaces if they don't exist yet
        self.bigip.icontrol.add_interfaces(['System.SystemInfo',
                                            'System.Statistics'])

        # iControl helper objects
        self.sys_info = self.bigip.icontrol.System.SystemInfo
        self.sys_stat = self.bigip.icontrol.System.Statistics

    @log
    def get_composite_score(self):
        cpu_score = self.get_cpu_health_score() * \
                    const.DEVICE_HEALTH_SCORE_CPU_WEIGHT
        mem_score = self.get_mem_health_score() * \
                    const.DEVICE_HEALTH_SCORE_MEM_WEIGHT
        cps_score = self.get_cps_health_score() * \
                    const.DEVICE_HEALTH_SCORE_CPS_WEIGHT

        total_weight = const.DEVICE_HEALTH_SCORE_CPU_WEIGHT + \
                       const.DEVICE_HEALTH_SCORE_MEM_WEIGHT + \
                       const.DEVICE_HEALTH_SCORE_CPS_WEIGHT

        return int((cpu_score + mem_score + cps_score) / total_weight)

    # returns percentage of TMM memory currently in use
    @log
    def get_mem_health_score(self):
        # use TMM memory usage for memory health
        stat_type = self.sys_stat.typefactory.create(
                                    'Common.StatisticType')

        for stat in self.sys_stat.get_all_tmm_statistics(
                                    ['0.0']).statistics[0].statistics:
            if stat.type == stat_type.STATISTIC_MEMORY_TOTAL_BYTES:
                total_memory = float(self.bigip.ulong_to_int(stat.value))
            if stat.type == stat_type.STATISTIC_MEMORY_USED_BYTES:
                used_memory = float(self.bigip.ulong_to_int(stat.value))

        if total_memory and used_memory:
            score = int(100 * \
                    ((total_memory - used_memory) / total_memory))
            return score
        else:
            return 0

    @log
    def get_cpu_health_score(self):
        cpu_stats = self.sys_info.get_cpu_usage_information()
        used_cycles = 1
        idle_cycles = 1

        for cpus in cpu_stats.usages:
            used_cycles += self.bigip.ulong_to_int(cpus.user)
            used_cycles += self.bigip.ulong_to_int(cpus.system)
            idle_cycles = self.bigip.ulong_to_int(cpus.idle)

        score = int(100 - \
                (100 * (float(used_cycles) / float(idle_cycles))))
        return score

    @log
    def get_cps_health_score(self):
        count_init = self._get_tcp_accepted_count()
        time.sleep(const.DEVICE_HEALTH_SCORE_CPS_PERIOD)
        count_final = self._get_tcp_accepted_count()
        cps = (count_final - count_init) \
              / const.DEVICE_HEALTH_SCORE_CPS_PERIOD

        if cps >= const.DEVICE_HEALTH_SCORE_CPS_MAX:
            return 0
        else:
            score = int(100 - ((100 * float(cps)) \
            / float(const.DEVICE_HEALTH_SCORE_CPS_MAX)))
        return score

    def _get_tcp_accepted_count(self):
        stat_type = self.sys_stat.typefactory.create(
                                    'Common.StatisticType')

        for stat in self.sys_stat.get_tcp_statistics().statistics:
            if stat.type == stat_type.STATISTIC_TCP_ACCEPTED_CONNECTIONS:
                return self.bigip.ulong_to_int(stat.value)
