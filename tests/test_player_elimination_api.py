from datetime import date

from app.extensions import db
from app.models import (
    Player,
    Tournament,
)
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


def create_running_tournament(
    app,
    *,
    bounty_enabled: bool,
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
            ]
        ]

        db.session.add_all(
            players
        )

        db.session.commit()

        tournament = create_tournament(
            name="API Test",
            tournament_date=date(
                2026,
                9,
                25,
            ),
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

        start_clock(
            tournament
        )

        return tournament.id


def test_eliminate_player_endpoint(
    client,
    app,
):
    tournament_id = (
        create_running_tournament(
            app,
            bounty_enabled=False,
        )
    )

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        entry_id = (
            tournament.players[0].id
        )

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/players/"
            f"{entry_id}/eliminate"
        ),
        json={},
    )

    assert response.status_code == 200

    payload = (
        response.get_json()
    )

    assert (
        payload[
            "players_remaining"
        ]
        == 2
    )


def test_bounty_elimination_endpoint(
    client,
    app,
):
    tournament_id = (
        create_running_tournament(
            app,
            bounty_enabled=True,
        )
    )

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        target_id = (
            tournament.players[0].id
        )

        killer_id = (
            tournament.players[1].id
        )

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/players/"
            f"{target_id}/eliminate"
        ),
        json={
            "eliminated_by_entry_id":
                killer_id,
        },
    )

    assert response.status_code == 200

    payload = (
        response.get_json()
    )

    killer = next(
        player
        for player in payload["players"]
        if player["entry_id"]
        == killer_id
    )

    assert (
        killer[
            "bounty_winnings"
        ]
        == 50
    )

    assert (
        killer[
            "bounty_count"
        ]
        == 1
    )


def test_restore_endpoint(
    client,
    app,
):
    tournament_id = (
        create_running_tournament(
            app,
            bounty_enabled=False,
        )
    )

    with app.app_context():
        tournament = (
            db.session.get(
                Tournament,
                tournament_id,
            )
        )

        target_id = (
            tournament.players[0].id
        )

    client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/players/"
            f"{target_id}/eliminate"
        ),
        json={},
    )

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/players/"
            f"{target_id}/restore"
        )
    )

    assert response.status_code == 200

    payload = (
        response.get_json()
    )

    assert (
        payload[
            "players_remaining"
        ]
        == 3
    )