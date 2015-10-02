from pyramid.config import Configurator

def main(global_config, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    
    # include the renderer for jinja2
    config.include('pyramid_jinja2')
    
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')
    config.add_route('new', '/new')
    config.add_route('apps', '/apps')
    config.add_route('app', 'app/{name}')
    
    # find the views defined in views.py
    config.scan()

    return config.make_wsgi_app()
