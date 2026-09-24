from datetime import date

from app.extensions import db
from app.models import Player
from app.services.clock_service import (
    start_clock,
)
from app.services.player_elimination import (
    eliminate_player,
)
from app.services.setup_service import (
    mark_tournament_ready,
)
from app.services.tournament_service import (
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def create_completed_game(
    app,
) -> tuple[int, int]:
    with app.app_context():
        elvis = Player(
            name="Elvis",
            name_key="elvis",
        )

        hugo = Player(
            name="Hugo",
            name_key="hugo",
        )

        db.session.add_all(
            [
                elvis,
                hugo,
            ]
        )

        db.session.commit()

        tournament = create_tournament(
            name="Profile Test",
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
                elvis.id,
                hugo.id,
            ],
        )

        ensure_tournament_structure(
            tournament
        )

        mark_tournament_ready(
            tournament
        )

        start_clock(
            tournament
        )

        eliminate_player(
            tournament=tournament,
            entry_id=(
                tournament.players[1].id
            ),
        )

        return (
            elvis.id,
            tournament.id,
        )


def test_player_profile_returns_200(
    client,
    app,
):
    (
        player_id,
        _,
    ) = create_completed_game(
        app
    )

    response = client.get(
        f"/players/{player_id}"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "PLAYER PROFILE" in page
    assert "Elvis" in page
    assert "Profile Test" in page


def test_dashboard_contains_real_statistics(
    client,
    app,
):
    create_completed_game(
        app
    )

    response = client.get(
        "/"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Leaderboards" in page
    assert "Elvis" in page
    assert "LATEST TOURNAMENT" in page


def test_history_contains_winner(
    client,
    app,
):
    (
        _,
        tournament_id,
    ) = create_completed_game(
        app
    )

    response = client.get(
        "/tournaments/"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Profile Test" in page
    assert "WINNER" in page
    assert "Elvis" in page

    assert (
        f"/tournaments/{tournament_id}/result"
        in page
    )