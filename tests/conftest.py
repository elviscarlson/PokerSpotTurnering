from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from config import TestingConfig


@pytest.fixture()
def app():
    app = create_app(TestingConfig)

    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()