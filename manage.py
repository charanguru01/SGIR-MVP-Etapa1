#!/usr/bin/env python
"""Punto de entrada administrativo de Django para el proyecto SGIR."""
import os
import sys


def main() -> None:
    """Ejecuta tareas administrativas del servidor SGIR."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sgir_config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
