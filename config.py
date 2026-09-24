from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"

INSTANCE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DEFAULT_DATABASE_PATH = (
    INSTANCE_DIR
    / "pokerspot.sqlite3"
)


class BaseConfig:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "development-secret-key",
    )

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get(
            "DATABASE_URL",
            (
                "sqlite:///"
                f"{DEFAULT_DATABASE_PATH}"
            ),
        )
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "timeout": 30,
        },
    }

    JSON_SORT_KEYS = False

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(
    BaseConfig
):
    DEBUG = True


class ProductionConfig(
    BaseConfig
):
    DEBUG = False
    TESTING = False

    SESSION_COOKIE_SECURE = True

    PREFERRED_URL_SCHEME = "https"

    @classmethod
    def validate(
        cls,
    ) -> None:
        secret_key = (
            os.environ.get(
                "SECRET_KEY",
                "",
            )
            .strip()
        )

        if not secret_key:
            raise RuntimeError(
                "SECRET_KEY must be set "
                "in production."
            )

        if (
            secret_key
            == "development-secret-key"
        ):
            raise RuntimeError(
                "Development SECRET_KEY "
                "cannot be used in production."
            )


class TestingConfig(
    BaseConfig
):
    TESTING = True
    DEBUG = False

    SECRET_KEY = (
        "testing-secret-key"
    )

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///:memory:"
    )

    SESSION_COOKIE_SECURE = False


Config = DevelopmentConfig