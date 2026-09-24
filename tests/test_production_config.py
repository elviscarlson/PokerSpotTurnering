import os

import pytest

from app import create_app
from config import (
    ProductionConfig,
)


def test_production_requires_secret_key(
    monkeypatch,
):
    monkeypatch.delenv(
        "SECRET_KEY",
        raising=False,
    )

    with pytest.raises(
        RuntimeError
    ):
        create_app(
            ProductionConfig
        )


def test_production_accepts_secret_key(
    monkeypatch,
):
    monkeypatch.setenv(
        "SECRET_KEY",
        (
            "test-production-secret-"
            "not-used-in-real-production"
        ),
    )

    app = create_app(
        ProductionConfig
    )

    assert (
        app.config["DEBUG"]
        is False
    )

    assert (
        app.config["TESTING"]
        is False
    )

    assert (
        app.config[
            "SESSION_COOKIE_SECURE"
        ]
        is True
    )


def test_database_path_is_absolute(
    monkeypatch,
):
    monkeypatch.setenv(
        "SECRET_KEY",
        "deployment-test-secret",
    )

    app = create_app(
        ProductionConfig
    )

    uri = app.config[
        "SQLALCHEMY_DATABASE_URI"
    ]

    assert uri.startswith(
        "sqlite:///"
    )

    assert (
        "pokerspot.sqlite3"
        in uri
    )