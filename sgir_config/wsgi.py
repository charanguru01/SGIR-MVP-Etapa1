"""Configuración WSGI para despliegue del servidor local SGIR."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sgir_config.settings")
application = get_wsgi_application()
