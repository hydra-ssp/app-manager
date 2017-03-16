from flask import Blueprint

appmanager = Blueprint('app_manager', __name__,
                       template_folder='templates',
                       static_folder='static/app_manager',
                       static_url_path='/apps/static')

from .views import *
