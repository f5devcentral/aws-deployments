"""Utilities"""
import subprocess


def get_cmd_output(cmd_array):
    """Get output from command"""
    proc = subprocess.Popen(cmd_array, stdout=subprocess.PIPE)
    retval = []
    for line in iter(proc.stdout.readline, ''):
        retval.append(line.rstrip())
    return retval
