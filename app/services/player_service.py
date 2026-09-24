from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Player


class PlayerError(ValueError):
    """Base exception for player validation errors."""


class InvalidPlayerNameError(PlayerError):
    """Raised when a player name is invalid."""


class PlayerAlreadyExistsError(PlayerError):
    """Raised when a player with the same normalized name already exists."""


def clean_player_name(name: str) -> str:
    """
    Normalize whitespace while preserving the player's chosen capitalization.

    Example:
        "  Elvis   Carlson  " -> "Elvis Carlson"
    """
    return " ".join(name.split())


def player_name_key(name: str) -> str:
    """
    Return the canonical key used to detect duplicate player names.

    Casefold is used rather than lower() because it is more robust for
    case-insensitive text comparison.
    """
    return clean_player_name(name).casefold()


def validate_player_name(name: str) -> str:
    cleaned_name = clean_player_name(name)

    if not cleaned_name:
        raise InvalidPlayerNameError("Spelarnamnet får inte vara tomt.")

    if len(cleaned_name) > 80:
        raise InvalidPlayerNameError(
            "Spelarnamnet får vara högst 80 tecken."
        )

    return cleaned_name


def create_player(name: str) -> Player:
    cleaned_name = validate_player_name(name)
    name_key = player_name_key(cleaned_name)

    existing_player = db.session.scalar(
        select(Player).where(Player.name_key == name_key)
    )

    if existing_player is not None:
        raise PlayerAlreadyExistsError(
            f"Spelaren {existing_player.name} finns redan."
        )

    player = Player(
        name=cleaned_name,
        name_key=name_key,
    )

    db.session.add(player)
    db.session.commit()

    return player


def update_player_name(
    player: Player,
    name: str,
) -> Player:
    cleaned_name = validate_player_name(name)
    name_key = player_name_key(cleaned_name)

    existing_player = db.session.scalar(
        select(Player).where(
            Player.name_key == name_key,
            Player.id != player.id,
        )
    )

    if existing_player is not None:
        raise PlayerAlreadyExistsError(
            f"Spelaren {existing_player.name} finns redan."
        )

    player.name = cleaned_name
    player.name_key = name_key

    db.session.commit()

    return player


def set_player_active(
    player: Player,
    is_active: bool,
) -> Player:
    player.is_active = is_active

    db.session.commit()

    return player