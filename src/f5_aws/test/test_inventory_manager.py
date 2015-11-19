"""
test_inventory_manager.py

In general, our approach to using ansible is to first progamatically
create the ansible inventory files for a deployment.  We do this using
the 'inventory_manager' role.  In some sense, the inventory provides a
"definition" of what is to be deployed. Various provisioning workflows
are executed given this environment inventory.

In this file we test that the correct inventory is created for various inputs.
While this seems slightly redundant, given the declarative syntax provided by
the Jinja2 template language, personal experience shows that it is pretty easy
to fatfinger the template files...

"""

import re
import sys
import json
import pytest
from time import time
from f5_aws.config import Config
from f5_aws.runner import EnvironmentManager, EnvironmentManagerFactory

config = Config().config
region_for_lifecyle_tests = config['regions'][0]
deployment_models = config['deployment_models']


def get_unique_test_inputs(deployment_model):
    timestamp = int(time())
    model_stages = {
        "single-standalone": {
            "init": {
                "inputs": {
                    "env_name": "ut-standalone-{}".format(timestamp),
                    "extra_vars": {
                        "deployment_model": "single-standalone",
                        "deployment_type": "lb_only",
                        "region": region_for_lifecyle_tests,
                        "zone": region_for_lifecyle_tests + "b"
                    },
                    "cmd": "init"
                }
            },
            "remove": {
                "inputs":
                {
                    "env_name": "ut-standalone-{}".format(timestamp),
                    "cmd": "remove"

                }
            },
        },
        "single-cluster": {
            "init": {
                "inputs": {
                    "env_name": "ut-cluster-{}".format(timestamp),
                    "extra_vars": {
                        "deployment_model": "single-cluster",
                        "deployment_type": "lb_only",
                        "region": region_for_lifecyle_tests,
                        "zone": region_for_lifecyle_tests + "b"
                    },
                    "cmd": "init"
  
                }
            },
            "remove": {
                "inputs":
                {
                    "env_name": "ut-cluster-{}".format(timestamp),
                    "cmd": "remove"
                }
            },
        },
        "cluster-per-zone": {
            "init": {
                "inputs": {
                    "env_name": "ut-cluster-per-zone-{}".format(timestamp),
                    "extra_vars": {
                        "deployment_model": "cluster-per-zone",
                        "deployment_type": "lb_only",
                        "region": region_for_lifecyle_tests,
                        "zones": [region_for_lifecyle_tests + "b", region_for_lifecyle_tests + "c"]
                    },
                    "cmd": "init"

                }
            },
            "remove": {
                "inputs":
                {
                    "env_name": "ut-cluster-per-zone-{}".format(timestamp),
                    "cmd": "remove"
                }
            }
        },
        "standalone-per-zone": {
            "init": {
                "inputs": {
                    "env_name": "ut-standalone-per-zone-{}".format(timestamp),
                    "extra_vars": {
                        "deployment_model": "standalone-per-zone",
                        "deployment_type": "lb_only",
                        "region": region_for_lifecyle_tests,
                        "zones": [region_for_lifecyle_tests + 'b', region_for_lifecyle_tests + "c"]
                    },
                    "cmd": "init"
                }
            },
            "remove": {
                "inputs": {
                    "env_name": "ut-standalone-per-zone-{}".format(timestamp),
                    "cmd": "remove"
                }
            }
        },
    }

    return model_stages[deployment_model]


def verify_deployment_model(deployment_model, inventory):
    if deployment_model == "single-standalone":
        verify_single_standalone(inventory)
    if deployment_model == "single-cluster":
        verify_single_cluster(inventory)
    if deployment_model == "standalone-per-zone":
        verify_standalone_per_zone(inventory)
    if deployment_model == "cluster-per-zone":
        verify_cluster_per_zone(inventory)


def verify_single_standalone(inventory):
    # there should be only a single zone
    zones = []
    for k in inventory.iterkeys():
        if re.match("^zone[0-9]$", k):
            zones.append(k)
    assert len(zones) == 1

    # there should be 1 bigip in this zone
    for zone in zones:
        bigips = []
        for host in inventory[zone]["hosts"]:
            if re.match("^zone[0-9]-bigip[0-9]$", host):
                bigips.append(host)
        assert len(bigips) == 1

    # one bigip in one cluster in one zone
    assert len(inventory["bigip-clusters"]["hosts"]) == 1
    assert len(inventory["bigip-cluster-seeds"]["hosts"]) == 1
    assert len(inventory[inventory["bigip-clusters"]
               ["hosts"][0]]["hosts"]) == 1


def verify_single_cluster(inventory):
    # there should be only a single zone
    zones = []
    for k in inventory.iterkeys():
        if re.match("^zone[0-9]$", k):
            zones.append(k)
    assert len(zones) == 1

    # there should be 2 bigips in this zone
    for zone in zones:
        bigips = []
        for host in inventory[zone]["hosts"]:
            if re.match("^zone[0-9]-bigip[0-9]$", host):
                bigips.append(host)
        assert len(bigips) == 2

    # two bigips in one cluster in one zone
    assert len(inventory["bigip-clusters"]["hosts"]) == 1
    assert len(inventory["bigip-cluster-seeds"]["hosts"]) == 1
    assert len(inventory[inventory["bigip-clusters"]
               ["hosts"][0]]["hosts"]) == 2


def verify_standalone_per_zone(inventory):
    # there should be two zones
    zones = []
    for k in inventory.iterkeys():
        if re.match("^zone[0-9]$", k):
            zones.append(k)
    assert len(zones) == 2

    # there should be 1 bigip in each zone
    for zone in zones:
        bigips = []
        for host in inventory[zone]["hosts"]:
            if re.match("^zone[0-9]-bigip[0-9]$", host):
                bigips.append(host)
        assert len(bigips) == 1

    # 1 bigip in each cluster
    assert len(inventory["bigip-clusters"]["hosts"]) == 2
    assert len(inventory["bigip-cluster-seeds"]["hosts"]) == 2
    for cluster in inventory["bigip-clusters"]["hosts"]:
        assert len(inventory[cluster]["hosts"]) == 1


def verify_cluster_per_zone(inventory):
    # there should be two zones
    zones = []
    for k in inventory.iterkeys():
        if re.match("^zone[0-9]$", k):
            zones.append(k)
    assert len(zones) == 2

    # there should be 4 bigips
    for zone in zones:
        bigips = []
        for host in inventory[zone]["hosts"]:
            if re.match("^zone[0-9]-bigip[0-9]$", host):
                bigips.append(host)
        assert len(bigips) == 2

    # 2 bigip in each cluster
    assert len(inventory["bigip-clusters"]["hosts"]) == 2
    assert len(inventory["bigip-cluster-seeds"]["hosts"]) == 2
    for cluster in inventory["bigip-clusters"]["hosts"]:
        assert len(inventory[cluster]["hosts"]) == 2

# scope=module => this setup function will be run once before
#  executing all the test methods in this module


@pytest.fixture(scope="function", params=deployment_models)
def model(request):
    return get_unique_test_inputs(request.param)


def test_inventory_lb_only(model):

    # initialize the inventory
    inputs = model["init"]["inputs"]
    inputs["cmd"] = "init"
    inputs["extra_vars"]["deployment_type"] = "lb_only"
    print inputs

    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "init")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)

    inventory = em.inventory()
    print inventory
    verify_deployment_model(model["init"]["inputs"]["extra_vars"][
                            "deployment_model"], inventory)

    assert inventory["all"]["vars"]["deployment_type"] == "lb_only"
    assert set(inventory["bigips"]["vars"]["modules"]) == set(["avr", "ltm"])

    # check we aren't provisioning additional modules for bigips running gtm
    if "gtms" in inventory:
        assert set(inventory["gtms"]["vars"]["modules"]) == set(["avr", "gtm"])

    # remove the inventory
    inputs = model["remove"]["inputs"]
    inputs["cmd"] = "remove"
    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "remove")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)


def test_inventory_lb_and_waf(model):

    # initialize the inventory
    inputs = model["init"]["inputs"]
    inputs["cmd"] = "init"
    inputs["extra_vars"]["deployment_type"] = "lb_and_waf"
    print inputs

    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "init")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)

    inventory = em.inventory()
    print inventory
    verify_deployment_model(model["init"]["inputs"]["extra_vars"][
                            "deployment_model"], inventory)

    assert inventory["all"]["vars"]["deployment_type"] == "lb_and_waf"
    assert set(inventory["bigips"]["vars"]["modules"]
               ) == set(["avr", "asm", "ltm"])
    if "gtms" in inventory:
        assert set(inventory["gtms"]["vars"]["modules"]) == set(["avr", "gtm"])

    # remove the inventory
    inputs = model["remove"]["inputs"]
    inputs["cmd"] = "remove"
    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "remove")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)


def test_inventory_w_analytics(model):
    """ default deployment_model is lb_only"""

    # initialize the inventory
    inputs = model["init"]["inputs"]
    inputs["cmd"] = "init"
    inputs["extra_vars"]["deploy_analytics"] = "true"
    print inputs

    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "init")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)

    inventory = em.inventory()
    print inventory
    verify_deployment_model(model["init"]["inputs"]["extra_vars"][
                            "deployment_model"], inventory)

    # check that we set the global deploy_analytics flag to true
    assert inventory["all"]["vars"]["deploy_analytics"] == "true"

    # check that *1* analytics host is being deployed
    assert len(inventory["analyticshosts"]["hosts"]) == 1

    # check that there is *1* analytics host in the all group..
    host = inventory["analyticshosts"]["hosts"][0]
    assert host in inventory["all"]['hosts']

    # remove the inventory
    inputs = model["remove"]["inputs"]
    inputs["cmd"] = "remove"
    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "remove")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)

def test_inventory_w_analytics_and_waf(model):

    # initialize the inventory
    inputs = model["init"]["inputs"]
    inputs["cmd"] = "init"
    inputs["extra_vars"]["deploy_analytics"] = "true"
    inputs["extra_vars"]["deployment_type"] = "lb_and_waf"
    print inputs

    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "init")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)

    inventory = em.inventory()
    print inventory
    verify_deployment_model(model["init"]["inputs"]["extra_vars"][
                            "deployment_model"], inventory)

    # check various things for analytics deployment
    assert inventory["all"]["vars"]["deploy_analytics"] == "true"
    assert len(inventory["analyticshosts"]["hosts"]) == 1
    host = inventory["analyticshosts"]["hosts"][0]
    assert host in inventory["all"]['hosts']

    # check various things for waf deployment
    assert inventory["all"]["vars"]["deployment_type"] == "lb_and_waf"
    assert set(inventory["bigips"]["vars"]["modules"]
               ) == set(["avr", "asm", "ltm"])
    if "gtms" in inventory:
        assert set(inventory["gtms"]["vars"]["modules"]) == set(["avr", "gtm"])

    # remove the inventory
    inputs = model["remove"]["inputs"]
    inputs["cmd"] = "remove"
    em = EnvironmentManagerFactory(**inputs)
    outputs = getattr(em, "remove")()
    assert (len(outputs["playbook_results"].playbooks) > 0 and
            outputs["playbook_results"].statuscode == 0)
