from datetime import date

from app.extensions import db
from app.models import Player
from app.services.clock_service import (
    start_clock,
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


def create_ready_tournament(
    app,
    *,
    bounty_enabled: bool = False,
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
            name="API Edge Test",
            tournament_date=date.today(),
            target_duration_minutes=180,
            buy_in=300,
            bounty_enabled=(
                bounty_enabled
            ),
            bounty_amount=(
                50
                if bounty_enabled
                else 0
            ),
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


def test_pause_before_start_returns_400(
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
            f"{tournament_id}/pause"
        )
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload["ok"] is False
    assert payload["error"]


def test_start_twice_returns_400(
    client,
    app,
):
    tournament_id = (
        create_ready_tournament(
            app
        )
    )

    first = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/start"
        )
    )

    assert first.status_code == 200

    second = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/start"
        )
    )

    assert second.status_code == 400


def test_invalid_adjust_time_payload_returns_400(
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

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/adjust-time"
        ),
        json={
            "delta_seconds":
                "not-a-number",
        },
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload["ok"] is False


def test_unknown_tournament_returns_404(
    client,
):
    response = client.get(
        "/api/tournaments/999999/state"
    )

    assert response.status_code == 404


def test_bounty_elimination_without_killer_returns_400(
    client,
    app,
):
    tournament_id = (
        create_ready_tournament(
            app,
            bounty_enabled=True,
        )
    )

    client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/start"
        )
    )

    with app.app_context():
        from app.models import Tournament

        tournament = db.session.get(
            Tournament,
            tournament_id,
        )

        target_id = (
            tournament.players[0].id
        )

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/players/"
            f"{target_id}/eliminate"
        ),
        json={},
    )

    assert response.status_code == 400

    assert (
        "bountyn"
        in response.get_json()[
            "error"
        ].lower()
    )