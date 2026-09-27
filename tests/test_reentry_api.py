from datetime import date

from app.extensions import db
from app.models import Player, Tournament
from app.services.clock_service import start_clock
from app.services.player_elimination import eliminate_player
from app.services.setup_service import mark_tournament_ready
from app.services.tournament_service import create_tournament
from app.services.tournament_structure import (
    ensure_tournament_structure,
)


def create_running_tournament(
    app,
) -> tuple[int, int]:
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
            name="Reentry API Test",
            tournament_date=date.today(),
            target_duration_minutes=240,
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

        hugo = tournament.players[1]

        eliminate_player(
            tournament=tournament,
            entry_id=hugo.id,
        )

        return (
            tournament.id,
            hugo.id,
        )


def test_reentry_endpoint(
    client,
    app,
):
    (
        tournament_id,
        hugo_id,
    ) = create_running_tournament(
        app
    )

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}"
            f"/players/"
            f"{hugo_id}"
            f"/reentry"
        )
    )

    assert response.status_code == 200

    payload = response.get_json()

    hugo = next(
        player
        for player
        in payload["players"]
        if (
            player["entry_id"]
            == hugo_id
        )
    )

    assert (
        hugo["status"]
        == "ACTIVE"
    )

    with app.app_context():
        tournament = db.session.get(
            Tournament,
            tournament_id,
        )

        entry = next(
            entry
            for entry
            in tournament.players
            if entry.id == hugo_id
        )

        assert (
            entry.buy_in_count
            == 2
        )

        assert (
            tournament.total_entries
            == 4
        )

        assert (
            tournament.total_buyins
            == 1200
        )


def test_active_player_cannot_reenter(
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
            name="Invalid Reentry",
            tournament_date=date.today(),
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

        tournament_id = tournament.id
        entry_id = tournament.players[0].id

    response = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}"
            f"/players/"
            f"{entry_id}"
            f"/reentry"
        )
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload["ok"] is False