from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.extensions import db
from app.models import (
    AppMeta,
    Player,
    Tournament,
)
from app.services.player_service import (
    create_player,
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


DEMO_SEED_KEY = "demo_seed_v1"

DEMO_PLAYER_NAMES = (
    "Elvis",
    "Hugo",
    "Leo",
    "Elias",
    "Philip",
    "Johan",
    "Anton",
    "Gustav",
)


def get_existing_demo_marker() -> AppMeta | None:
    return db.session.scalar(
        select(AppMeta).where(
            AppMeta.key
            == DEMO_SEED_KEY
        )
    )


def get_or_create_player(
    name: str,
) -> Player:
    name_key = (
        name.strip().casefold()
    )

    player = db.session.scalar(
        select(Player).where(
            Player.name_key
            == name_key
        )
    )

    if player is not None:
        if not player.is_active:
            player.is_active = True
            db.session.commit()

        return player

    return create_player(
        name
    )


def seed_demo_data() -> Tournament:
    existing_marker = (
        get_existing_demo_marker()
    )

    if existing_marker is not None:
        tournament_id = int(
            existing_marker.value
        )

        tournament = db.session.get(
            Tournament,
            tournament_id,
        )

        if tournament is not None:
            return tournament

        db.session.delete(
            existing_marker
        )

        db.session.commit()

    players = [
        get_or_create_player(
            name
        )
        for name in DEMO_PLAYER_NAMES
    ]

    tournament = create_tournament(
        name="Friday Poker",
        tournament_date=date.today(),
        target_duration_minutes=240,
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

    marker = AppMeta(
        key=DEMO_SEED_KEY,
        value=str(
            tournament.id
        ),
    )

    db.session.add(
        marker
    )

    db.session.commit()

    return tournament