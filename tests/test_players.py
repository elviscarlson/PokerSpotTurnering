from app.extensions import db
from app.models import Player


def test_players_page_returns_200(
    client,
):
    response = client.get(
        "/players/"
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Spelare" in page
    assert "PLAYER REGISTRY" in page


def test_add_player(
    client,
    app,
):
    response = client.post(
        "/players/",
        data={
            "name": "Elvis",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Elvis" in page

    with app.app_context():
        player = db.session.scalar(
            db.select(
                Player
            )
            .where(
                Player.name_key
                == "elvis"
            )
        )

        assert player is not None
        assert player.name == "Elvis"
        assert player.is_active is True


def test_duplicate_player_is_rejected(
    client,
    app,
):
    client.post(
        "/players/",
        data={
            "name": "Elvis",
        },
    )

    response = client.post(
        "/players/",
        data={
            "name": "  ELVIS  ",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert (
        "finns redan"
        in page
    )

    with app.app_context():
        players = db.session.scalars(
            db.select(
                Player
            )
        ).all()

        assert len(players) == 1


def test_edit_player(
    client,
    app,
):
    with app.app_context():
        player = Player(
            name="Elvis",
            name_key="elvis",
        )

        db.session.add(
            player
        )

        db.session.commit()

        player_id = player.id

    response = client.post(
        f"/players/{player_id}/edit",
        data={
            "name": "Elvis Carlson",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    page = response.get_data(
        as_text=True
    )

    assert "Elvis Carlson" in page

    with app.app_context():
        player = db.session.get(
            Player,
            player_id,
        )

        assert player is not None

        assert (
            player.name
            == "Elvis Carlson"
        )

        assert (
            player.name_key
            == "elvis carlson"
        )


def test_archive_player(
    client,
    app,
):
    with app.app_context():
        player = Player(
            name="Elvis",
            name_key="elvis",
        )

        db.session.add(
            player
        )

        db.session.commit()

        player_id = player.id

    response = client.post(
        (
            f"/players/"
            f"{player_id}/"
            f"toggle-active"
        ),
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        player = db.session.get(
            Player,
            player_id,
        )

        assert player is not None
        assert player.is_active is False


def test_restore_player(
    client,
    app,
):
    with app.app_context():
        player = Player(
            name="Elvis",
            name_key="elvis",
            is_active=False,
        )

        db.session.add(
            player
        )

        db.session.commit()

        player_id = player.id

    response = client.post(
        (
            f"/players/"
            f"{player_id}/"
            f"toggle-active"
        ),
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        player = db.session.get(
            Player,
            player_id,
        )

        assert player is not None
        assert player.is_active is True