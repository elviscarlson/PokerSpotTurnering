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


def create_ready_game(
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
            name="Route Flow",
            tournament_date=date.today(),
            target_duration_minutes=180,
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

        mark_tournament_ready(
            tournament
        )

        return tournament.id


def test_http_flow_ready_to_completed(
    client,
    app,
):
    tournament_id = (
        create_ready_game(
            app
        )
    )


    admin = client.get(
        (
            f"/tournaments/"
            f"{tournament_id}/admin"
        )
    )

    assert (
        admin.status_code
        == 200
    )


    started = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/start"
        )
    )

    assert (
        started.status_code
        == 200
    )

    assert (
        started.get_json()[
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

        elvis = (
            tournament.players[0]
        )

        hugo = (
            tournament.players[1]
        )

        elvis_id = elvis.id
        hugo_id = hugo.id


    completed = client.post(
        (
            f"/api/tournaments/"
            f"{tournament_id}/players/"
            f"{hugo_id}/eliminate"
        ),
        json={
            "eliminated_by_entry_id":
                elvis_id,
        },
    )


    assert (
        completed.status_code
        == 200
    )

    payload = (
        completed.get_json()
    )

    assert (
        payload["status"]
        == "COMPLETED"
    )

    assert (
        payload["winner"]["name"]
        == "Elvis"
    )


    result = client.get(
        (
            f"/tournaments/"
            f"{tournament_id}/result"
        )
    )

    assert (
        result.status_code
        == 200
    )

    page = result.get_data(
        as_text=True
    )

    assert (
        "TOURNAMENT COMPLETED"
        in page
    )

    assert "Elvis" in page
    assert "Hugo" in page


    history = client.get(
        "/tournaments/"
    )

    assert (
        history.status_code
        == 200
    )

    history_page = (
        history.get_data(
            as_text=True
        )
    )

    assert "Route Flow" in history_page
    assert "WINNER" in history_page
    assert "Elvis" in history_page