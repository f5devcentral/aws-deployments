#!/usr/bin/python
# (C) 2012, Chris Mutzel, <c.mutzel@f5.com>

#  This is a modified version of ansible-playbook

import sys
import os
import stat

# Augment PYTHONPATH to find Python modules relative to this file path
# This is so that we can find the modules when running from a local checkout
# installed as editable with `pip install -e ...` or `python setup.py develop`
local_module_path = os.path.abspath(
	os.path.join(os.path.dirname(__file__), '..', 'lib')
)
sys.path.append(local_module_path)

import ansible.playbook
import ansible.constants as C
import ansible.utils.template
from ansible import errors
from ansible import callbacks
from ansible import utils
from ansible.color import ANSIBLE_COLOR, stringc
from ansible.callbacks import display

def colorize(lead, num, color):
	""" Print 'lead' = 'num' in 'color' """
	if num != 0 and ANSIBLE_COLOR and color is not None:
		return "%s%s%-15s" % (stringc(lead, color), stringc("=", color), stringc(str(num), color))
	else:
		return "%s=%-4s" % (lead, str(num))

def hostcolor(host, stats, color=True):
	if ANSIBLE_COLOR and color:
		if stats['failures'] != 0 or stats['unreachable'] != 0:
			return "%-37s" % stringc(host, 'red')
		elif stats['changed'] != 0:
			return "%-37s" % stringc(host, 'yellow')
		else:
			return "%-37s" % stringc(host, 'green')
	return "%-26s" % host


def main(args, playsbooks):
	''' run ansible-playbook operations '''

	# create parser for CLI options
	parser = utils.base_parser(
		constants=C,
		usage = "%prog playbook.yml",
		connect_opts=True,
		runas_opts=True,
		subset_opts=True,
		check_opts=True,
		diff_opts=True
	)
	#parser.add_option('--vault-password', dest="vault_password",
	#    help="password for vault encrypted files")
	parser.add_option('-e', '--extra-vars', dest="extra_vars", action="append",
		help="set additional variables as key=value or YAML/JSON", default=[])
	parser.add_option('-t', '--tags', dest='tags', default='all',
		help="only run plays and tasks tagged with these values")
	parser.add_option('--skip-tags', dest='skip_tags',
		help="only run plays and tasks whose tags do not match these values")
	parser.add_option('--syntax-check', dest='syntax', action='store_true',
		help="perform a syntax check on the playbook, but do not execute it")
	parser.add_option('--list-tasks', dest='listtasks', action='store_true',
		help="list all tasks that would be executed")
	parser.add_option('--step', dest='step', action='store_true',
		help="one-step-at-a-time: confirm each task before running")
	parser.add_option('--start-at-task', dest='start_at',
		help="start the playbook at the task matching this name")
	parser.add_option('--force-handlers', dest='force_handlers', action='store_true',
		help="run handlers even if a task fails")
	parser.add_option('--flush-cache', dest='flush_cache', action='store_true',
		help="clear the fact cache")

	options, args = parser.parse_args(args)


	sshpass = None
	sudopass = None
	su_pass = None
	vault_pass = None


	for playbook in playbooks:
		if not os.path.exists(playbook):
			raise errors.AnsibleError("the playbook: %s could not be found" % playbook)
		if not (os.path.isfile(playbook) or stat.S_ISFIFO(os.stat(playbook).st_mode)):
			raise errors.AnsibleError("the playbook: %s does not appear to be a file" % playbook)


	for playbook in playbooks:

		stats = callbacks.AggregateStats()
		playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
		if options.step:
			playbook_cb.step = options.step
		if options.start_at:
			playbook_cb.start_at = options.start_at
		runner_cb = callbacks.PlaybookRunnerCallbacks(stats, verbose=utils.VERBOSITY)

		#reload the inventory before running each playbook
		inventory = ansible.inventory.Inventory(options.inventory, vault_password=vault_pass)
		inventory.subset(options.subset)

		if len(inventory.list_hosts()) == 0:
			raise errors.AnsibleError("provided hosts list is empty")

		pb = ansible.playbook.PlayBook(
			playbook=playbook,
			module_path=options.module_path,
			inventory=inventory,
			forks=options.forks,
			remote_user=options.remote_user,
			remote_pass=sshpass,
			callbacks=playbook_cb,
			runner_callbacks=runner_cb,
			stats=stats,
			timeout=options.timeout,
			transport=options.connection,
			sudo=options.sudo,
			sudo_user=options.sudo_user,
			sudo_pass=sudopass,
			#extra_vars=extra_vars,
			private_key_file=options.private_key_file,
			#only_tags=only_tags,
			#skip_tags=skip_tags,
			check=options.check,
			diff=options.diff,
			su=options.su,
			su_pass=su_pass,
			su_user=options.su_user,
			vault_password=vault_pass,
			force_handlers=options.force_handlers
		)

		if options.flush_cache:
			display(callbacks.banner("FLUSHING FACT CACHE"))
			pb.SETUP_CACHE.flush()

		if options.listhosts or options.listtasks or options.syntax:
			print ''
			print 'playbook: %s' % playbook
			print ''
			playnum = 0
			for (play_ds, play_basedir) in zip(pb.playbook, pb.play_basedirs):
				playnum += 1
				play = ansible.playbook.Play(pb, play_ds, play_basedir,
											  vault_password=pb.vault_password)
				label = play.name
				hosts = pb.inventory.list_hosts(play.hosts)

				# Filter all tasks by given tags
				if pb.only_tags != 'all':
					if options.subset and not hosts:
						continue
					matched_tags, unmatched_tags = play.compare_tags(pb.only_tags)

					# Remove skipped tasks
					matched_tags = matched_tags - set(pb.skip_tags)

					unmatched_tags.discard('all')
					unknown_tags = ((set(pb.only_tags) | set(pb.skip_tags)) -
									(matched_tags | unmatched_tags))

					if unknown_tags:
						continue

				if options.listhosts:
					print '  play #%d (%s): host count=%d' % (playnum, label, len(hosts))
					for host in hosts:
						print '    %s' % host

				if options.listtasks:
					print '  play #%d (%s):' % (playnum, label)

					for task in play.tasks():
						if (set(task.tags).intersection(pb.only_tags) and not
							set(task.tags).intersection(pb.skip_tags)):
							if getattr(task, 'name', None) is not None:
								# meta tasks have no names
								print '    %s' % task.name
				if options.listhosts or options.listtasks:
					print ''
			continue

		if options.syntax:
			# if we've not exited by now then we are fine.
			print 'Playbook Syntax is fine'
			return 0

		failed_hosts = []
		unreachable_hosts = []

		try:

			pb.run()

			hosts = sorted(pb.stats.processed.keys())
			display(callbacks.banner("PLAY RECAP"))
			playbook_cb.on_stats(pb.stats)

			for h in hosts:
				t = pb.stats.summarize(h)
				if t['failures'] > 0:
					failed_hosts.append(h)
				if t['unreachable'] > 0:
					unreachable_hosts.append(h)

			retries = failed_hosts + unreachable_hosts

			if len(retries) > 0:
				filename = pb.generate_retry_inventory(retries)
				if filename:
					display("           to retry, use: --limit @%s\n" % filename)

			for h in hosts:
				t = pb.stats.summarize(h)

				display("%s : %s %s %s %s" % (
					hostcolor(h, t),
					colorize('ok', t['ok'], 'green'),
					colorize('changed', t['changed'], 'yellow'),
					colorize('unreachable', t['unreachable'], 'red'),
					colorize('failed', t['failures'], 'red')),
					screen_only=True
				)

				display("%s : %s %s %s %s" % (
					hostcolor(h, t, False),
					colorize('ok', t['ok'], None),
					colorize('changed', t['changed'], None),
					colorize('unreachable', t['unreachable'], None),
					colorize('failed', t['failures'], None)),
					log_only=True
				)


			print ""
			if len(failed_hosts) > 0:
				return 2
			if len(unreachable_hosts) > 0:
				return 3

		except errors.AnsibleError, e:
			display("ERROR: %s" % e, color='red')
			return 1

	return 0


if __name__ == "__main__":
	display(" ", log_only=True)
	display(" ".join(sys.argv), log_only=True)
	display(" ", log_only=True)
	try:
		playbooks = ['./bin/deploy_vpc.yml', './bin/deploy_az.yml', './bin/deploy_bigip.yml']
		sys.exit(main(sys.argv[1:], playbooks))
	except errors.AnsibleError, e:
		display("ERROR: %s" % e, color='red', stderr=True)
		sys.exit(1)
	except KeyboardInterrupt, ke:
		display("ERROR: interrupted", color='red', stderr=True)
		sys.exit(1)
