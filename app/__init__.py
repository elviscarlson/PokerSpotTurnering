from __future__ import annotations

from pathlib import Path

from flask import Flask

from config import (
    DevelopmentConfig,
    ProductionConfig,
)

from .extensions import db


def create_app(
    config_object: type | object | None = None,
) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
    )

    selected_config = (
        config_object
        or DevelopmentConfig
    )

    app.config.from_object(
        selected_config
    )

    if (
        selected_config
        is ProductionConfig
    ):
        ProductionConfig.validate()

    Path(
        app.instance_path
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    db.init_app(
        app
    )

    register_blueprints(
        app
    )

    register_commands(
        app
    )

    return app


def register_blueprints(
    app: Flask,
) -> None:
    from .routes.api import api_bp
    from .routes.main import main_bp
    from .routes.players import (
        players_bp,
    )
    from .routes.tournaments import (
        tournaments_bp,
    )

    app.register_blueprint(
        main_bp
    )

    app.register_blueprint(
        players_bp
    )

    app.register_blueprint(
        tournaments_bp
    )

    app.register_blueprint(
        api_bp
    )


def register_commands(
    app: Flask,
) -> None:
    @app.cli.command(
        "init-db"
    )
    def init_db() -> None:
        """Create all database tables."""
        with app.app_context():
            db.create_all()

        print(
            "Database initialized."
        )


    @app.cli.command(
        "seed-demo"
    )
    def seed_demo() -> None:
        """Create PokerSpot demo data."""
        from .services.demo_seed import (
            seed_demo_data,
        )

        with app.app_context():
            db.create_all()

            tournament = (
                seed_demo_data()
            )

            print(
                "Demo data ready."
            )

            print(
                (
                    "Tournament: "
                    f"{tournament.name}"
                )
            )

            print(
                (
                    "Players: "
                    f"{tournament.player_count}"
                )
            )

            print(
                (
                    "Buy-in: "
                    f"{tournament.buy_in} kr"
                )
            )

            print(
                (
                    "Bounty: "
                    f"{tournament.bounty_amount} kr"
                )
            )

            print(
                (
                    "Status: "
                    f"{tournament.status}"
                )
            )

            print(
                (
                    "Open: "
                    f"/tournaments/"
                    f"{tournament.id}/admin"
                )
            )