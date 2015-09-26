import json
import f5_aws
import f5_aws.utils as utils
import f5_aws.runner as runner
import f5_aws.utils 
from pyramid.view import view_config

@view_config(route_name='home', renderer='templates/home.jinja2')
def home_view(request):
    return {'project': 'service_catalog'}

@view_config(route_name='new_app', renderer='templates/new_app.jinja2')
def new_app_view(request):
    # this page will allow a post method for which will create
    #  a new environment
    return {'project': 'service_catalog'}

@view_config(route_name='my_apps', renderer='templates/my_apps.jinja2')
def my_apps_view(request):
    # get a list of the environments
    envs = []
    names = runner.EnvironmentManager.get_envs()

    for i in names:
        em = runner.EnvironmentManager(utils.get_namespace(env_name=i, cmd='info'))
        inventory, resources, statuses = em.get_environment_info()
        login_info = em.login_info()
        
        envs.append({
            'name': i,
            'inventory': inventory,
            'resources': resources,
            'statuses': statuses,
            'login_info': login_info
        })

    #  and the the corrosponding inventories, resources, and login information
    # pass this as a python dictionary to the my_apps template
    # the html page we return should provide the ability to 
    # 1) select whether or not WAF is deployed
    # 2) "redeploy" an architecture 
    # 3) teardown the architecture
    # 4) delete deployment 

    return {'envs': envs, 'project': 'service_catalog', 'request': request}