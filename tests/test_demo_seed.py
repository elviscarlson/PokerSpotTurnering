from app.extensions import db
from app.models import (
    AppMeta,
    Player,
    Tournament,
)
from app.services.demo_seed import (
    DEMO_PLAYER_NAMES,
    DEMO_SEED_KEY,
    seed_demo_data,
)


def test_demo_seed_creates_expected_tournament(
    app,
):
    with app.app_context():
        tournament = (
            seed_demo_data()
        )

        assert (
            tournament.name
            == "Friday Poker"
        )

        assert (
            tournament.player_count
            == 8
        )

        assert (
            tournament.buy_in
            == 300
        )

        assert (
            tournament.bounty_enabled
            is True
        )

        assert (
            tournament.bounty_amount
            == 50
        )

        assert (
            tournament.target_duration_minutes
            == 240
        )

        assert (
            tournament.status
            == "READY"
        )


def test_demo_seed_creates_expected_players(
    app,
):
    with app.app_context():
        seed_demo_data()

        names = {
            player.name
            for player in db.session.scalars(
                db.select(
                    Player
                )
            ).all()
        }

        assert names == set(
            DEMO_PLAYER_NAMES
        )


def test_demo_seed_is_idempotent(
    app,
):
    with app.app_context():
        first = (
            seed_demo_data()
        )

        second = (
            seed_demo_data()
        )

        assert (
            first.id
            == second.id
        )

        tournaments = (
            db.session.scalars(
                db.select(
                    Tournament
                )
            ).all()
        )

        players = (
            db.session.scalars(
                db.select(
                    Player
                )
            ).all()
        )

        markers = (
            db.session.scalars(
                db.select(
                    AppMeta
                )
                .where(
                    AppMeta.key
                    == DEMO_SEED_KEY
                )
            ).all()
        )

        assert len(
            tournaments
        ) == 1

        assert len(
            players
        ) == 8

        assert len(
            markers
        ) == 1