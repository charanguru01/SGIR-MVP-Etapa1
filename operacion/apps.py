"""Configuración de la aplicación principal de operación del restaurante."""
from django.apps import AppConfig


class OperacionConfig(AppConfig):
    """Define metadatos de la app operacion del SGIR."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "operacion"
    verbose_name = "Operación SGIR Etapa 1"
