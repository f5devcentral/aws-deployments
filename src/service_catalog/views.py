import re
import json
import colander
import deform
from html import HTML
from pyramid.view import view_config
from deform import Form, ValidationFailure, widget
from pyramid.httpexceptions import HTTPFound

import f5_aws
import f5_aws.runner as runner
from f5_aws.config import Config
from f5_aws.job_manager import JobManager


def check_env_name(value):
    if not value or not re.match("^[a-zA-z]{1}[a-zA-Z0-9-]*", value):
        return False
    return True

def make_pretty(value):
    return value.replace("-", " ").replace("_"," ").upper()

def compose_form_tags(form):
    # include the required headers for our form view
    #  in all structs sent to the renderers
    resources = form.get_widget_resources()
    js_resources = resources["js"]
    css_resources = resources["css"]
    js_links = [ "/static/%s" % r for r in js_resources ]
    css_links = [ "/static/%s" % r for r in css_resources ]
    js_tags = ["<script type='text/javascript' src='%s'></script>" % link
               for link in js_links]
    css_tags = ["<link rel='stylesheet' href='%s'/>" % link
               for link in css_links]
    tags = "\n".join(js_tags + css_tags)

    return tags

def compute_provisioning_status(statuses):
    provisioning_status = "Deployed"
    for k, v in statuses.iteritems():
        if v != "deployed":
            provisioning_status = "Not deployed/error"
    return provisioning_status


@view_config(route_name="home", renderer="service_catalog:templates/home.jinja2")
def home_view(request):
    return {"project": "service_catalog"}

@view_config(route_name="new", renderer="service_catalog:templates/new.jinja2")
def new_app_view(request):
    """
    View provides a form method to create a new environment.
    We use 'deform', a technology for form  rendering and validation. 
    """
    
    #build the form
    config = Config().config
    aws_region_values = [(i, make_pretty(i)) for i in config["regions"]]
    deployment_model_values = [(i, make_pretty(i)) for i in config["deployment_models"]]
    deployment_type_values = [(i, make_pretty(i)) for i in config["deployment_types"]]
    container_id_values = [(i, make_pretty(i)) for i in config["available_apps"]]

    class AppDeployment(colander.MappingSchema):
        env_name = colander.SchemaNode(colander.String(),
                       title="Deployment Name",
                       validator=colander.Function(check_env_name)
        )
        region = colander.SchemaNode(colander.String(),
                       title="AWS Region",
                       widget = widget.SelectWidget(values=aws_region_values),
                       validator = colander.OneOf(config["regions"])
        )
        container_id = colander.SchemaNode(colander.String(),
                       title="Container ID", 
                       widget = widget.SelectWidget(values=container_id_values),
                       validator = colander.OneOf(config["available_apps"])
        )
        deployment_type = colander.SchemaNode(colander.String(),
                       title="Deployment Type", 
                       widget = widget.SelectWidget(values=deployment_type_values),
                       validator = colander.OneOf(config["deployment_types"])
        )
        deployment_model = colander.SchemaNode(colander.String(),
                       title="Deployment Footprint", 
                       widget = widget.SelectWidget(values=deployment_model_values),
                       validator = colander.OneOf(config["deployment_models"])
        )

    class Schema(colander.MappingSchema):
        app_deployment = AppDeployment()

    schema = Schema()

    # by default, or form submit button posts to this page
    form = Form(schema, buttons=("submit",))
    tags = compose_form_tags(form)
    
    # If we got a post, someone submitted the form.  Render 
    #  the page based on whether we recieved good inputs.
    if "submit" in request.POST:
        controls = request.POST.items()
        try:
            appstruct = form.validate(controls) 
            inputs = appstruct["app_deployment"]
            
            # initialize this environment and redirect
            # to the deployemnts page if successful
            em = runner.EnvironmentManagerFactory(
                cmd="init",
                env_name=inputs["env_name"],
                extra_vars = {
                    "deployment_model": inputs['deployment_model'],
                    "deployment_type": inputs['deployment_type'],
                    "region": inputs['region'],
                    "zone": (inputs['region'] + 'b'),
                    "image_id": inputs['container_id']
                }
            )
            result = em.init()
            if (result["playbook_results"] and
                result["playbook_results"].statuscode == 0):

                # submit a job to provision this environment
                jm = JobManager()
                em = runner.EnvironmentManagerFactory(
                    cmd="deploy",
                    env_name=inputs["env_name"] 
                )
                jm.submit_request(em.deploy)
                
                # redirect
                return HTTPFound(location="/apps")

        except ValidationFailure as e:
            # form validation failed
            # re-render the form with an exception
            return {
                "project": "service_catalog",
                "form": e.render(),
                "tags": tags
            } 

        except Exception as e:
            import traceback
            import sys
            
            # show detailed errors
            return {
                "project": "service_catalog",
                "errors": [str(e), traceback.format_exc(), sys.exc_info()[0]],
                "tags": tags
            }

    # base case - render the form
    return {"project": "service_catalog",
            "form": form.render(),
            "tags": tags}

@view_config(route_name="apps", renderer="service_catalog:templates/apps.jinja2")
def all_apps_view(request):
    """
    View that displays all environments on a single page within a table. 
    Provide link to more details for each. 
    """
    jm = JobManager()

    # list of strings for the table header
    table_header = [] 
    # list of list of strings for each table row
    table_rows = [] 
    names = runner.EnvironmentManager.get_envs()
    if names:
        for i, name in enumerate(names):
            # information on the environment
            em = runner.EnvironmentManagerFactory(env_name=name, cmd="info")
            inventory, resources, statuses = em.get_environment_info()
            env_info = em.get_env_info(inventory)
            provisioning_status = compute_provisioning_status(statuses)
            last_status = jm.get_request_status(name)

            #build the table header
            if i == 0:
                table_header.append("NAME")
                keys = env_info.keys()
                for k in keys:
                    table_header.append(k.upper())
                table_header.append("STATUS")

            # build the table row data for this env
            row = []
            row.append(name)
            for k in keys:
                row.append(env_info[k])
            row.append(provisioning_status)
            table_rows.append(row)

    return {"project": "service_catalog",
            "table_header": table_header,
            "table_rows": table_rows}

@view_config(route_name="app", renderer="service_catalog:templates/app.jinja2")
def single_app_view(request):
    """
    View showing detailed information about a single deployment.  
    Allows the ability to re-deploy, teardown, or remove.
    """

    # pyramid route matching gives access to uri vars
    name = request.matchdict["name"]

    # get information about our environment that we want to display
    em = runner.EnvironmentManagerFactory(env_name=name, cmd="info")
    inventory, resources, statuses = em.get_environment_info()
    env_info = em.get_env_info(inventory)
    login_info = em.login_info()
    provisioning_status = compute_provisioning_status(statuses)
    
    jm = JobManager()
    status = jm.get_request_status(name)
        
    # just use deform to provide the buttons
    class Schema(colander.MappingSchema):
        pass

    # these buttons redirect to the same page,
    #  but trigger a background job to be executed
    buttons = (
        {"name": "Re-deploy", "value": "deploy"},
        {"name": "Teardown", "value": "teardown"},
        {"name": "Remove", "value": "remove"}
    )
    # createt the buttons
    for b in buttons:
        b['button'] = deform.Button(
            name=b["name"],
            value=b["value"])
    
    # create the form and add the buttons to the form
    schema = Schema()
    form = Form(schema,
        buttons=[button["button"] for button in buttons])
    tags = compose_form_tags(form)
    form = form.render()

    # if there was a post to the page, react to the button
    for b in buttons:
        if b["name"] in request.POST:        
            print "Triggering action '{}' of for environment {}".format(
                b["value"], name)
            em = runner.EnvironmentManagerFactory(
                cmd=b["value"],
                env_name=name
            )
            jm.submit_request(getattr(em, b["value"]))

    return {
        "project": "service_catalog",
        "tags": tags,
        "form": form,
        "name": name,
        "status": provisioning_status,
        "msg": status["msg"],
        "error": status["err"], 
        "last_update": status["last_update"], 
        "env_info": env_info,
        "login_info": login_info,
        "statuses": statuses
    }
