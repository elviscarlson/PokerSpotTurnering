from app.extensions import db
from app.models import (
    Player,
    Tournament,
)
from app.services.tournament_service import (
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def create_test_tournament(
    app,
) -> int:
    with app.app_context():
        players = [
            Player(
                name=name,
                name_key=name.casefold(),
            )
            for name in [
                "Elvis",
                "Hugo",
                "Leo",
                "Elias",
                "Philip",
            ]
        ]

        db.session.add_all(
            players
        )

        db.session.commit()

        tournament = create_tournament(
            name="Friday Poker",
            tournament_date=(
                __import__(
                    "datetime"
                ).date(
                    2026,
                    9,
                    25,
                )
            ),
            target_duration_minutes=240,
            buy_in=300,
            bounty_enabled=True,
            bounty_amount=50,
            player_ids=[
                player.id
                for player in players
            ],
        )

        ensure_tournament_structure(
            tournament
        )

        return tournament.id


def test_setup_can_be_saved(
    client,
    app,
):
    tournament_id = (
        create_test_tournament(
            app
        )
    )

    response = client.post(
        (
            f"/tournaments/"
            f"{tournament_id}/"
            f"setup/save"
        ),
        data={
            "starting_stack": "20000",
            "payout_amount": [
                "750",
                "500",
            ],
            "small_blind": [
                "25",
                "50",
                "100",
            ],
            "big_blind": [
                "50",
                "100",
                "200",
            ],
            "duration_minutes": [
                "15",
                "15",
                "15",
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        "Turneringsstrukturen sparades."
        in response.get_data(
            as_text=True
        )
    )

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        assert tournament is not None

        assert (
            tournament.structure.starting_stack
            == 20_000
        )


def test_invalid_payout_is_rejected(
    client,
    app,
):
    tournament_id = (
        create_test_tournament(
            app
        )
    )

    response = client.post(
        (
            f"/tournaments/"
            f"{tournament_id}/"
            f"setup/save"
        ),
        data={
            "starting_stack": "15000",
            "payout_amount": [
                "1000",
                "500",
            ],
            "small_blind": [
                "25",
                "50",
            ],
            "big_blind": [
                "50",
                "100",
            ],
            "duration_minutes": [
                "15",
                "15",
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        "Summan av priserna måste vara exakt samma som prispotten."
        in response.get_data(
            as_text=True
        )
    )


def test_tournament_can_be_marked_ready(
    client,
    app,
):
    tournament_id = (
        create_test_tournament(
            app
        )
    )

    response = client.post(
        (
            f"/tournaments/"
            f"{tournament_id}/"
            f"setup/ready"
        ),
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        assert tournament is not None

        assert (
            tournament.status
            == "READY"
        )


def test_regenerate_sets_draft(
    client,
    app,
):
    tournament_id = (
        create_test_tournament(
            app
        )
    )

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        tournament.status = "READY"

        db.session.commit()

    response = client.post(
        (
            f"/tournaments/"
            f"{tournament_id}/"
            f"setup/regenerate"
        ),
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        assert tournament is not None

        assert (
            tournament.status
            == "DRAFT"
        )