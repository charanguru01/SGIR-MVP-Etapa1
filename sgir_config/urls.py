"""Enrutamiento raíz del servidor SGIR."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("operacion.urls")),
]
