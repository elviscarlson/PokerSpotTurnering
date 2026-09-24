from datetime import date

from app.extensions import db
from app.models import Player
from app.services.setup_service import (
    mark_tournament_ready,
)
from app.services.tournament_service import (
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def create_ready_tournament(
    app,
) -> int:
    with app.app_context():
        players = [
            Player(
                name="Elvis",
                name_key="elvis",
            ),
            Player(
                name="Hugo",
                name_key="hugo",
            ),
        ]

        db.session.add_all(
            players
        )

        db.session.commit()

        tournament = create_tournament(
            name="Premium UI Test",
            tournament_date=date(
                2026,
                9,
                24,
            ),
            target_duration_minutes=180,
            buy_in=300,
            bounty_enabled=False,
            bounty_amount=0,
            player_ids=[
                player.id
                for player in players
            ],
        )

        ensure_tournament_structure(
            tournament
        )

        mark_tournament_ready(
            tournament
        )

        return tournament.id


def test_global_navigation(
    client,
):
    response = client.get(
        "/"
    )

    assert (
        response.status_code
        == 200
    )

    page = response.get_data(
        as_text=True
    )

    assert "POKERSPOT" in page
    assert "Dashboard" in page
    assert "Turneringar" in page
    assert "Spelare" in page
    assert "Ny turnering" in page


def test_admin_has_primary_actions(
    client,
    app,
):
    tournament_id = (
        create_ready_tournament(
            app
        )
    )

    response = client.get(
        (
            f"/tournaments/"
            f"{tournament_id}/admin"
        )
    )

    page = response.get_data(
        as_text=True
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        "Start tournament"
        in page
    )

    assert "Pause" in page
    assert "Next →" in page
    assert "Open Display" in page


def test_display_remains_standalone(
    client,
    app,
):
    tournament_id = (
        create_ready_tournament(
            app
        )
    )

    response = client.get(
        (
            f"/tournaments/"
            f"{tournament_id}/display"
        )
    )

    page = response.get_data(
        as_text=True
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        "ENTER FULLSCREEN"
        in page
    )

    assert (
        "Ny turnering"
        not in page
    )