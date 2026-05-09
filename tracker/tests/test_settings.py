import os
from unittest.mock import patch

from django.test import SimpleTestCase

from physio_project import settings


class EnvironmentSettingsTests(SimpleTestCase):
    def test_env_list_splits_comma_separated_values(self):
        with patch.dict(os.environ, {
            "CORS_ALLOWED_ORIGINS": "http://localhost:3000, http://127.0.0.1:3000"
        }):
            values = settings.env_list("CORS_ALLOWED_ORIGINS")

        self.assertEqual(values, ["http://localhost:3000", "http://127.0.0.1:3000"])

    def test_env_bool_accepts_common_true_values(self):
        for value in ["1", "true", "yes", "on"]:
            with self.subTest(value=value):
                with patch.dict(os.environ, {"CORS_ALLOW_CREDENTIALS": value}):
                    self.assertTrue(settings.env_bool("CORS_ALLOW_CREDENTIALS"))

    def test_env_bool_uses_default_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(settings.env_bool("CORS_ALLOW_CREDENTIALS", default=False))


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
