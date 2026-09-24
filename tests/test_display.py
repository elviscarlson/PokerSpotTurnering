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
            Player(
                name="Leo",
                name_key="leo",
            ),
        ]

        db.session.add_all(
            players
        )

        db.session.commit()

        tournament = create_tournament(
            name="Display Test",
            tournament_date=date(
                2026,
                9,
                25,
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


def test_display_page_returns_200(
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

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Display Test" in page
    assert "ENTER FULLSCREEN" in page
    assert "POKERSPOT" in page


def test_draft_cannot_open_display(
    client,
    app,
):
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
            name="Draft Test",
            tournament_date=date(
                2026,
                9,
                25,
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

        tournament_id = (
            tournament.id
        )

    response = client.get(
        (
            f"/tournaments/"
            f"{tournament_id}/display"
        ),
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        "Turneringen måste vara READY"
        in response.get_data(
            as_text=True
        )
    )