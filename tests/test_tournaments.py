from datetime import date

from app.extensions import db
from app.models import (
    Player,
    Prize,
    Tournament,
)


def create_player(
    name: str,
) -> Player:
    player = Player(
        name=name,
        name_key=name.casefold(),
    )

    db.session.add(
        player
    )

    return player


def test_tournament_list_returns_200(
    client,
):
    response = client.get(
        "/tournaments/"
    )

    assert response.status_code == 200

    assert (
        "Turneringar"
        in response.get_data(
            as_text=True
        )
    )


def test_new_tournament_page_returns_200(
    client,
):
    response = client.get(
        "/tournaments/new"
    )

    assert response.status_code == 200

    assert (
        "Skapa turnering"
        in response.get_data(
            as_text=True
        )
    )


def test_create_tournament(
    client,
    app,
):
    with app.app_context():
        elvis = create_player(
            "Elvis"
        )

        hugo = create_player(
            "Hugo"
        )

        db.session.commit()

        elvis_id = elvis.id
        hugo_id = hugo.id

    response = client.post(
        "/tournaments/new",
        data={
            "name": "Friday Poker",
            "tournament_date": "2026-09-25",
            "duration_hours": "4",
            "duration_minutes": "0",
            "buy_in": "300",
            "player_ids": [
                str(elvis_id),
                str(hugo_id),
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Friday Poker" in page
    assert "600" in page

    with app.app_context():
        tournament = db.session.scalar(
            db.select(
                Tournament
            )
        )

        assert tournament is not None

        assert (
            tournament.name
            == "Friday Poker"
        )

        assert (
            tournament.tournament_date
            == date(
                2026,
                9,
                25,
            )
        )

        assert (
            tournament.target_duration_minutes
            == 240
        )

        assert tournament.buy_in == 300

        assert (
            tournament.player_count
            == 2
        )

        assert (
            tournament.total_buyins
            == 600
        )

        assert (
            tournament.regular_prize_pool
            == 600
        )

        assert (
            tournament.bounty_pool
            == 0
        )

        assert len(
            tournament.prizes
        ) == 1

        assert (
            tournament.total_prizes
            == 600
        )


def test_create_bounty_tournament(
    client,
    app,
):
    with app.app_context():
        elvis = create_player(
            "Elvis"
        )

        hugo = create_player(
            "Hugo"
        )

        leo = create_player(
            "Leo"
        )

        db.session.commit()

        player_ids = [
            elvis.id,
            hugo.id,
            leo.id,
        ]

    response = client.post(
        "/tournaments/new",
        data={
            "name": "Bounty Night",
            "tournament_date": "2026-09-25",
            "duration_hours": "4",
            "duration_minutes": "0",
            "buy_in": "300",
            "bounty_enabled": "on",
            "bounty_amount": "50",
            "player_ids": [
                str(player_id)
                for player_id
                in player_ids
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        tournament = db.session.scalar(
            db.select(
                Tournament
            )
        )

        assert tournament is not None

        assert (
            tournament.total_buyins
            == 900
        )

        assert (
            tournament.bounty_pool
            == 150
        )

        assert (
            tournament.regular_prize_pool
            == 750
        )

        assert (
            tournament.total_prizes
            == 750
        )

        assert (
            tournament.total_prizes
            + tournament.bounty_pool
            == tournament.total_buyins
        )


def test_five_player_payout_is_persisted(
    client,
    app,
):
    with app.app_context():
        players = [
            create_player(name)
            for name in [
                "Elvis",
                "Hugo",
                "Leo",
                "Elias",
                "Philip",
            ]
        ]

        db.session.commit()

        player_ids = [
            player.id
            for player in players
        ]

    response = client.post(
        "/tournaments/new",
        data={
            "name": "Friday Poker",
            "tournament_date": "2026-09-25",
            "duration_hours": "4",
            "duration_minutes": "0",
            "buy_in": "300",
            "bounty_enabled": "on",
            "bounty_amount": "50",
            "player_ids": [
                str(player_id)
                for player_id
                in player_ids
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        tournament = db.session.scalar(
            db.select(
                Tournament
            )
        )

        assert tournament is not None

        assert (
            tournament.regular_prize_pool
            == 1_250
        )

        assert len(
            tournament.prizes
        ) == 2

        assert [
            prize.amount
            for prize in tournament.prizes
        ] == [
            800,
            450,
        ]

        assert (
            tournament.total_prizes
            == 1_250
        )


def test_prize_records_exist_in_database(
    client,
    app,
):
    with app.app_context():
        players = [
            create_player(name)
            for name in [
                "Elvis",
                "Hugo",
                "Leo",
                "Elias",
                "Philip",
            ]
        ]

        db.session.commit()

        player_ids = [
            player.id
            for player in players
        ]

    client.post(
        "/tournaments/new",
        data={
            "name": "Friday Poker",
            "tournament_date": "2026-09-25",
            "duration_hours": "4",
            "duration_minutes": "0",
            "buy_in": "300",
            "player_ids": [
                str(player_id)
                for player_id
                in player_ids
            ],
        },
    )

    with app.app_context():
        prizes = db.session.scalars(
            db.select(Prize).order_by(
                Prize.place
            )
        ).all()

        assert len(prizes) == 2

        assert sum(
            prize.amount
            for prize in prizes
        ) == 1_500


def test_bounty_cannot_equal_buy_in(
    client,
    app,
):
    with app.app_context():
        elvis = create_player(
            "Elvis"
        )

        hugo = create_player(
            "Hugo"
        )

        db.session.commit()

        player_ids = [
            elvis.id,
            hugo.id,
        ]

    response = client.post(
        "/tournaments/new",
        data={
            "name": "Bad Bounty",
            "tournament_date": "2026-09-25",
            "duration_hours": "4",
            "duration_minutes": "0",
            "buy_in": "300",
            "bounty_enabled": "on",
            "bounty_amount": "300",
            "player_ids": [
                str(player_id)
                for player_id
                in player_ids
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        "Bountyn måste vara lägre än buy-in."
        in response.get_data(
            as_text=True
        )
    )

    with app.app_context():
        tournament_count = (
            db.session.scalar(
                db.select(
                    db.func.count(
                        Tournament.id
                    )
                )
            )
        )

        assert tournament_count == 0


def test_tournament_requires_two_players(
    client,
    app,
):
    with app.app_context():
        elvis = create_player(
            "Elvis"
        )

        db.session.commit()

        elvis_id = elvis.id

    response = client.post(
        "/tournaments/new",
        data={
            "name": "Solo Poker",
            "tournament_date": "2026-09-25",
            "duration_hours": "4",
            "duration_minutes": "0",
            "buy_in": "300",
            "player_ids": [
                str(elvis_id),
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        "Välj minst två spelare."
        in response.get_data(
            as_text=True
        )
    )


def test_archived_player_cannot_enter_tournament(
    client,
    app,
):
    with app.app_context():
        elvis = create_player(
            "Elvis"
        )

        hugo = create_player(
            "Hugo"
        )

        hugo.is_active = False

        db.session.commit()

        elvis_id = elvis.id
        hugo_id = hugo.id

    response = client.post(
        "/tournaments/new",
        data={
            "name": "Friday Poker",
            "tournament_date": "2026-09-25",
            "duration_hours": "4",
            "duration_minutes": "0",
            "buy_in": "300",
            "player_ids": [
                str(elvis_id),
                str(hugo_id),
            ],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        "kunde inte användas"
        in response.get_data(
            as_text=True
        )
    )