from pyramid.config import Configurator

def main(global_config, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    config.include('pyramid_chameleon')
    config.add_static_view('static', 'static', cache_max_age=3600)
    #config.add_static_view('static', 'deform:static')
    config.add_route('home', '/')
    config.add_route('new_app', '/new')
    config.add_route('my_apps', '/myapps')
    config.scan()
    config.include('pyramid_jinja2')
    return config.make_wsgi_app()
