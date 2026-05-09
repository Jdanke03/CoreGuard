import os
from unittest.mock import patch

from django.test import SimpleTestCase

from physio_project import settings


class DatabaseSettingsTests(SimpleTestCase):
    def test_database_config_defaults_to_sqlite(self):
        with patch.dict(os.environ, {}, clear=True):
            config = settings.database_config()

        self.assertEqual(config["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertTrue(str(config["default"]["NAME"]).endswith("db.sqlite3"))

    def test_database_config_supports_postgres_url(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgres://coreguard:secret@example.com:5432/coreguard_db"
        }):
            config = settings.database_config()

        database = config["default"]
        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(database["NAME"], "coreguard_db")
        self.assertEqual(database["USER"], "coreguard")
        self.assertEqual(database["PASSWORD"], "secret")
        self.assertEqual(database["HOST"], "example.com")
        self.assertEqual(database["PORT"], 5432)
