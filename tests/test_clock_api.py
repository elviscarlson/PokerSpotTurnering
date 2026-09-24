from datetime import date

from app.extensions import db
from app.models import Player, Tournament
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
            name="Clock Test",
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


def test_state_endpoint(
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
            f"/api/tournaments/"
            f"{tournament_id}/state"
        )
    )

    assert response.status_code == 200

    payload = (
        response.get_json()
    )

    assert (
        payload["status"]
        == "READY"
    )

    assert (
        payload[
            "current_level"
        ][
            "position"
        ]
        == 1
    )


def test_start_endpoint(
    client,
    app,
):
    tournament_id = (
        create_ready_tournament(
            app
        )
    )

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/start"
        )
    )

    assert response.status_code == 200

    assert (
        response.get_json()[
            "status"
        ]
        == "RUNNING"
    )

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        assert (
            tournament.status
            == "RUNNING"
        )


def test_pause_and_resume_endpoints(
    client,
    app,
):
    tournament_id = (
        create_ready_tournament(
            app
        )
    )

    client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/start"
        )
    )

    pause_response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/pause"
        )
    )

    assert (
        pause_response
        .get_json()[
            "status"
        ]
        == "PAUSED"
    )

    resume_response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/resume"
        )
    )

    assert (
        resume_response
        .get_json()[
            "status"
        ]
        == "RUNNING"
    )


def test_adjust_time_endpoint(
    client,
    app,
):
    tournament_id = (
        create_ready_tournament(
            app
        )
    )

    client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/start"
        )
    )

    before = client.get(
        (
            f"/api/tournaments/"
            f"{tournament_id}/state"
        )
    ).get_json()

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/adjust-time"
        ),
        json={
            "delta_seconds": 300,
        },
    )

    assert response.status_code == 200

    after = response.get_json()

    assert (
        after[
            "remaining_seconds"
        ]
        >=
        before[
            "remaining_seconds"
        ]
        + 299
    )