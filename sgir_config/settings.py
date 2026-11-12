"""
Configuración principal del servidor SGIR (Etapa 1 - MVP).
Diseñado para operación autónoma en red local (LAN) con controles OWASP Top 10.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# En producción local se carga desde variable de entorno
SECRET_KEY = os.environ.get(
    "SGIR_SECRET_KEY",
    "sgir-lan-dev-key-cambiar-en-despliegue-local-2026",
)

DEBUG = os.environ.get("SGIR_DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]  # Permite acceso desde tablets y cajas en la red local (LAN)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "operacion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sgir_config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "sgir_config.wsgi.application"

# Base de datos local (SQLite por defecto para portabilidad; soporta PostgreSQL en LAN)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_sgir_local.sqlite3",
    }
}

# Endurecimiento de sesiones y cabeceras (OWASP A01 / A05)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 28800  # 8 horas (duración máxima de turno)
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
