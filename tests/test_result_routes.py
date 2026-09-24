from datetime import date

from app.extensions import db
from app.models import Player, Tournament
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


def create_completed_tournament(
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
            name="Final Table",
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

        start_clock(
            tournament
        )

        eliminate_player(
            tournament=tournament,
            entry_id=(
                tournament.players[1].id
            ),
        )

        return tournament.id


def test_result_page_returns_200(
    client,
    app,
):
    tournament_id = (
        create_completed_tournament(
            app
        )
    )

    response = client.get(
        (
            f"/tournaments/"
            f"{tournament_id}/result"
        )
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "FINAL RESULTS" in page
    assert "Elvis" in page
    assert "Hugo" in page
    assert "TOURNAMENT COMPLETED" in page


def test_admin_redirects_to_result_when_complete(
    client,
    app,
):
    tournament_id = (
        create_completed_tournament(
            app
        )
    )

    response = client.get(
        (
            f"/tournaments/"
            f"{tournament_id}/admin"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 302

    assert (
        f"/tournaments/{tournament_id}/result"
        in response.headers["Location"]
    )


def test_result_undo_reopens_tournament(
    client,
    app,
):
    tournament_id = (
        create_completed_tournament(
            app
        )
    )

    response = client.post(
        (
            f"/tournaments/"
            f"{tournament_id}/result/"
            f"undo-last"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 302

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
            in (
                "RUNNING",
                "PAUSED",
            )
        )

        assert (
            tournament.active_player_count
            == 2
        )