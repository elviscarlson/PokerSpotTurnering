from __future__ import annotations

import os

from app import create_app
from config import (
    DevelopmentConfig,
    ProductionConfig,
)


def get_config():
    environment = (
        os.environ.get(
            "APP_ENV",
            "development",
        )
        .strip()
        .lower()
    )

    if environment == "production":
        return ProductionConfig

    return DevelopmentConfig


app = create_app(
    get_config()
)


if __name__ == "__main__":
    app.run(
        debug=app.config["DEBUG"],
    )