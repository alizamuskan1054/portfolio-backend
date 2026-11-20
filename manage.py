#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    # Local development uses the dev settings by default.
    # `manage.py test` always uses the isolated test settings (local SQLite, never Neon).
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        default_settings = "config.settings.test"
    elif os.environ.get("VERCEL"):
        # Vercel runs manage.py to discover the settings module: use production settings there.
        default_settings = "config.settings.prod"
    else:
        default_settings = "config.settings.dev"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django is not installed. Activate your virtualenv and run "
            "'pip install -r requirements.txt'."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
