"""
This file executes playbooks using ansible python APIs
"""

import re
import os
import stat
import time

# ansible stuff
import ansible.playbook

from ansible import errors
from ansible import callbacks
from ansible import utils
from ansible.color import ANSIBLE_COLOR, stringc
from ansible.callbacks import display

from f5_aws.config import Config

# make our config global
config = Config().config


def hostcolor(host, stats, color=True):
    if ANSIBLE_COLOR and color:
        if stats["failures"] != 0 or stats["unreachable"] != 0:
            return "%-37s" % stringc(host, "red")
        elif stats["changed"] != 0:
            return "%-37s" % stringc(host, "yellow")
        else:
            return "%-37s" % stringc(host, "green")
    return "%-26s" % host


def colorize(lead, num, color):
    """ Print 'lead' = 'num' in 'color' """
    if num != 0 and ANSIBLE_COLOR and color is not None:
        return "%s%s%-15s" % (stringc(lead, color),
                              stringc("=", color), stringc(str(num), color))
    else:
        return "%s=%-4s" % (lead, str(num))


class PlaybookRunner(object):
    """
      This class is used to execute a set of ansible playbooks
        included in ./playbooks.
      Playbooks are executed using the run method, which reloads the
      inventory between each playbook.  This is slightly different than the
      way that ansible-playbook command typically handles things.  It only loads
      the inventory once for a set of playbooks. 
    """
    config = config

    def __init__(self, playbooks, settings, inventory_path, options, extra_vars):

        self.inventory_path = inventory_path
        self.extra_vars = extra_vars
        self.playbooks = playbooks
        self.runtime = 0  # seconds

        # Ansible defaults carried over from `ansible-playbook`.
        self.options = options
        self.options.forks = ansible.constants.DEFAULT_FORKS
        self.options.module_path = ansible.constants.DEFAULT_MODULE_PATH
        self.options.remote_user = ansible.constants.DEFAULT_REMOTE_USER
        self.options.timeout = ansible.constants.DEFAULT_TIMEOUT
        self.options.connection = ansible.constants.DEFAULT_TRANSPORT
        self.options.sudo = ansible.constants.DEFAULT_SUDO
        self.options.sudo_user = None
        self.options.su = ansible.constants.DEFAULT_SU
        self.options.su_user = ansible.constants.DEFAULT_SU_USER
        self.options.check = False
        self.options.diff = False
        self.options.force_handlers = False
        self.options.flush_cache = False
        self.options.listhosts = False
        self.options.listtasks = False
        self.options.syntax = False

    def print_playbook_results(self):
        if self.statuscode == 0:
          display_color = 'green'
        else:
          display_color = 'red'
        display("Ran playbooks {}. \n Total time was {}".format(self.playbooks,
          datetime.timedelta(seconds=self.runtime)), color=display_color)

    def run(self):
        """
          This is a modified version of the function used within ansible-playbook.
        """

        tstart = time.time()

        # get the absolute path for the playbooks
        self.playbooks = [
            "{}/playbooks/{}".format(config["install_path"], pb) for pb in self.playbooks]

        # Ansible defaults carried over from `ansible-playbook`.
        sshpass = None
        sudopass = None
        su_pass = None
        vault_pass = None

        for playbook in self.playbooks:
            if not os.path.exists(playbook):
                raise errors.AnsibleError(
                    "the playbook: %s could not be found" % playbook)
            if not (os.path.isfile(playbook) or stat.S_ISFIFO(os.stat(playbook).st_mode)):
                raise errors.AnsibleError(
                    "the playbook: %s does not appear to be a file" % playbook)

        for playbook in self.playbooks:
            display("Running playbook: %s" %
                    playbook, color="green", stderr=False)

            stats = callbacks.AggregateStats()
            playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
            runner_cb = callbacks.PlaybookRunnerCallbacks(
                stats, verbose=utils.VERBOSITY)
            inventory = ansible.inventory.Inventory(
                self.inventory_path, vault_password=vault_pass)

            if len(inventory.list_hosts()) == 0:
                raise errors.AnsibleError("provided hosts list is empty")

            pb = ansible.playbook.PlayBook(
                playbook=playbook,
                module_path=self.options.module_path,
                inventory=inventory,
                forks=self.options.forks,
                remote_user=self.options.remote_user,
                remote_pass=sshpass,
                callbacks=playbook_cb,
                runner_callbacks=runner_cb,
                stats=stats,
                timeout=self.options.timeout,
                transport=self.options.connection,
                sudo=self.options.sudo,
                sudo_user=self.options.sudo_user,
                sudo_pass=sudopass,
                extra_vars=self.extra_vars,
                check=self.options.check,
                diff=self.options.diff,
                su=self.options.su,
                su_pass=su_pass,
                su_user=self.options.su_user,
                vault_password=vault_pass,
                force_handlers=self.options.force_handlers
            )

            failed_hosts = []
            unreachable_hosts = []

            try:
                pb.run()

                hosts = sorted(pb.stats.processed.keys())
                display(callbacks.banner("PLAY RECAP"))
                playbook_cb.on_stats(pb.stats)

                for h in hosts:
                    t = pb.stats.summarize(h)
                    if t["failures"] > 0:
                        failed_hosts.append(h)
                    if t["unreachable"] > 0:
                        unreachable_hosts.append(h)

                retries = failed_hosts + unreachable_hosts

                if len(retries) > 0:
                    filename = pb.generate_retry_inventory(retries)
                    if filename:
                        display(
                            "     to retry, use: --limit @%s\n" % filename)

                for h in hosts:
                    t = pb.stats.summarize(h)

                    display("%s : %s %s %s %s" % (
                        hostcolor(h, t),
                        colorize("ok", t["ok"], "green"),
                        colorize("changed", t["changed"], "yellow"),
                        colorize("unreachable", t["unreachable"], "red"),
                        colorize("failed", t["failures"], "red")),
                        screen_only=True
                    )

                    display("%s : %s %s %s %s" % (
                        hostcolor(h, t, False),
                        colorize("ok", t["ok"], None),
                        colorize("changed", t["changed"], None),
                        colorize("unreachable", t["unreachable"], None),
                        colorize("failed", t["failures"], None)),
                        log_only=True
                    )

                print ""
                tend = time.time()
                self.runtime = tend - tstart

                if len(failed_hosts) > 0:
                    self.statuscode = 2
                    return

                if len(unreachable_hosts) > 0:
                    self.statuscode = 3
                    return

                self.statuscode = 0

            except errors.AnsibleError, e:
                display("ERROR: %s" % e, color="red")
                self.statuscode = 1
                return

        self.statuscode = 0
