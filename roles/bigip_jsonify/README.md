bigip-jsonify
=============

This role will JSONify a BIG-IP device so that it can be orchestrated natively
with ansible.

The whole point of needing this role in the first place is because versions of
BIG-IP <= 11.6.0 have two problems

    1. The version of python installed is very old (2.4.3)
    2. There is no json module available

The JSON module itself because a part of python core in version 2.6. Versions
older than that can usually install the simplejson module from pip. The problem
however is that even simplejson only supports versions of python 2.5 and up.

So you're at an impasse here because you have a super old version of python
and you can't get a json module.

Furthering the problem, if you try to manually install an older version of
simplejson that DOES support older versions of python, you will be beaten by
the BIG-IP because it mounts its /usr partition as read-only. Effectively
prohibiting you from installing python modules. :-/

So this module works around all of that, installs an old copy of simplejson
and sets up 11.6.0 versions (and probably earlier) of BIG-IP so that that
can directly be orchestrated by ansible
