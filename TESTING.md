# Running the tests

    python manage.py test --settings=config.settings.test            # everything
    python manage.py test apps.accounts --settings=config.settings.test   # one app
    python manage.py test apps.accounts.tests.test_auth_api.LoginTests --settings=config.settings.test -v 2
    python manage.py test --settings=config.settings.test --failfast  # stop on first failure
    python manage.py test --settings=config.settings.test --parallel  # faster

Tests use in-memory SQLite, local temp media and locmem email: your Neon DB and Cloudinary are never touched.
Tests / classes with `RISK` in the name probe suspected bugs; a failure there means a real bug to fix.
