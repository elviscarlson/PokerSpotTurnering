from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Player,
    Prize,
    Tournament,
    TournamentPlayer,
)
from app.services.prize_structure import (
    generate_payout_structure,
)


class TournamentError(ValueError):
    pass


class InvalidTournamentError(TournamentError):
    pass


def clean_tournament_name(
    name: str,
) -> str:
    return " ".join(
        name.split()
    )


def validate_tournament_name(
    name: str,
) -> str:
    cleaned_name = clean_tournament_name(
        name
    )

    if not cleaned_name:
        raise InvalidTournamentError(
            "Turneringen måste ha ett namn."
        )

    if len(cleaned_name) > 120:
        raise InvalidTournamentError(
            "Turneringsnamnet får vara högst 120 tecken."
        )

    return cleaned_name


def validate_buy_in(
    buy_in: int,
) -> int:
    if buy_in <= 0:
        raise InvalidTournamentError(
            "Buy-in måste vara större än 0 kr."
        )

    if buy_in > 1_000_000:
        raise InvalidTournamentError(
            "Buy-in är orimligt högt."
        )

    return buy_in


def validate_target_duration(
    target_duration_minutes: int,
) -> int:
    if target_duration_minutes <= 0:
        raise InvalidTournamentError(
            "Turneringslängden måste vara större än 0 minuter."
        )

    if (
        target_duration_minutes
        > 24 * 60
    ):
        raise InvalidTournamentError(
            "Turneringslängden får inte överstiga 24 timmar."
        )

    return target_duration_minutes


def validate_bounty(
    *,
    bounty_enabled: bool,
    bounty_amount: int,
    buy_in: int,
) -> int:
    if not bounty_enabled:
        return 0

    if bounty_amount <= 0:
        raise InvalidTournamentError(
            "Ange ett bountybelopp."
        )

    if bounty_amount >= buy_in:
        raise InvalidTournamentError(
            "Bountyn måste vara lägre än buy-in."
        )

    return bounty_amount


def get_active_players_by_ids(
    player_ids: list[int],
) -> list[Player]:
    unique_player_ids = list(
        dict.fromkeys(
            player_ids
        )
    )

    if len(unique_player_ids) < 2:
        raise InvalidTournamentError(
            "Välj minst två spelare."
        )

    players = db.session.scalars(
        select(Player).where(
            Player.id.in_(
                unique_player_ids
            ),
            Player.is_active.is_(True),
        )
    ).all()

    players_by_id = {
        player.id: player
        for player in players
    }

    ordered_players = [
        players_by_id[player_id]
        for player_id
        in unique_player_ids
        if player_id
        in players_by_id
    ]

    if (
        len(ordered_players)
        != len(unique_player_ids)
    ):
        raise InvalidTournamentError(
            "En eller flera valda spelare kunde inte användas."
        )

    return ordered_players


def create_tournament(
    *,
    name: str,
    tournament_date: date,
    target_duration_minutes: int,
    buy_in: int,
    bounty_enabled: bool,
    bounty_amount: int,
    player_ids: list[int],
) -> Tournament:
    cleaned_name = (
        validate_tournament_name(
            name
        )
    )

    buy_in = validate_buy_in(
        buy_in
    )

    target_duration_minutes = (
        validate_target_duration(
            target_duration_minutes
        )
    )

    bounty_amount = validate_bounty(
        bounty_enabled=bounty_enabled,
        bounty_amount=bounty_amount,
        buy_in=buy_in,
    )

    players = get_active_players_by_ids(
        player_ids
    )

    tournament = Tournament(
        name=cleaned_name,
        tournament_date=tournament_date,
        target_duration_minutes=(
            target_duration_minutes
        ),
        buy_in=buy_in,
        bounty_enabled=bounty_enabled,
        bounty_amount=bounty_amount,
        status="DRAFT",
    )

    for player in players:
        tournament.players.append(
            TournamentPlayer(
                player=player,
                status="ACTIVE",
            )
        )

    prize_pool = (
        len(players)
        * (
            buy_in
            - bounty_amount
        )
    )

    payout_structure = (
        generate_payout_structure(
            prize_pool=prize_pool,
            number_of_players=len(
                players
            ),
        )
    )

    for suggestion in payout_structure:
        tournament.prizes.append(
            Prize(
                place=suggestion.place,
                amount=suggestion.amount,
            )
        )

    if (
        sum(
            prize.amount
            for prize in tournament.prizes
        )
        != prize_pool
    ):
        raise AssertionError(
            "Generated prizes do not equal the regular prize pool."
        )

    db.session.add(
        tournament
    )

    db.session.commit()

    return tournament