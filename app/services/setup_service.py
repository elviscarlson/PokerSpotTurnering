from __future__ import annotations

from collections.abc import Sequence

from app.extensions import db
from app.models import BlindLevel, Tournament


class SetupError(ValueError):
    pass


def validate_starting_stack(
    starting_stack: int,
) -> int:
    if starting_stack < 1_000:
        raise SetupError(
            "Startstacken måste vara minst 1 000."
        )

    if starting_stack > 10_000_000:
        raise SetupError(
            "Startstacken är orimligt hög."
        )

    if starting_stack % 25 != 0:
        raise SetupError(
            "Startstacken måste vara delbar med 25."
        )

    return starting_stack


def validate_payouts(
    *,
    tournament: Tournament,
    payouts: Sequence[int],
) -> list[int]:
    if not payouts:
        raise SetupError(
            "Minst en betald placering krävs."
        )

    if len(payouts) > tournament.player_count:
        raise SetupError(
            "Antalet priser kan inte överstiga antalet spelare."
        )

    normalized = [
        int(amount)
        for amount in payouts
    ]

    if any(
        amount <= 0
        for amount in normalized
    ):
        raise SetupError(
            "Alla priser måste vara större än 0 kr."
        )

    if normalized != sorted(
        normalized,
        reverse=True,
    ):
        raise SetupError(
            "Priserna måste vara fallande från första plats."
        )

    if (
        sum(normalized)
        != tournament.regular_prize_pool
    ):
        raise SetupError(
            "Summan av priserna måste vara exakt samma som prispotten."
        )

    return normalized


def validate_blind_levels(
    levels: Sequence[
        tuple[int, int, int]
    ],
) -> list[
    tuple[int, int, int]
]:
    if not levels:
        raise SetupError(
            "Minst en blindnivå krävs."
        )

    normalized: list[
        tuple[int, int, int]
    ] = []

    previous_small = 0
    previous_big = 0

    for (
        small_blind,
        big_blind,
        duration_minutes,
    ) in levels:
        if (
            small_blind <= 0
            or big_blind <= 0
        ):
            raise SetupError(
                "Blinds måste vara större än 0."
            )

        if small_blind >= big_blind:
            raise SetupError(
                "Small blind måste vara lägre än big blind."
            )

        if duration_minutes <= 0:
            raise SetupError(
                "Nivåtiden måste vara större än 0 minuter."
            )

        if duration_minutes > 120:
            raise SetupError(
                "En blindnivå får inte vara längre än 120 minuter."
            )

        if (
            small_blind <= previous_small
            or big_blind <= previous_big
        ):
            raise SetupError(
                "Blindnivåerna måste öka för varje level."
            )

        normalized.append(
            (
                small_blind,
                big_blind,
                duration_minutes,
            )
        )

        previous_small = small_blind
        previous_big = big_blind

    return normalized


def update_payouts(
    *,
    tournament: Tournament,
    payouts: Sequence[int],
) -> None:
    normalized = validate_payouts(
        tournament=tournament,
        payouts=payouts,
    )

    if len(normalized) != len(
        tournament.prizes
    ):
        for prize in list(
            tournament.prizes
        ):
            db.session.delete(
                prize
            )

        db.session.flush()

        from app.models import Prize

        for place, amount in enumerate(
            normalized,
            start=1,
        ):
            tournament.prizes.append(
                Prize(
                    place=place,
                    amount=amount,
                )
            )

    else:
        for prize, amount in zip(
            tournament.prizes,
            normalized,
            strict=True,
        ):
            prize.amount = amount


def update_structure(
    *,
    tournament: Tournament,
    starting_stack: int,
    blind_levels: Sequence[
        tuple[int, int, int]
    ],
) -> None:
    if tournament.structure is None:
        raise SetupError(
            "Turneringsstrukturen saknas."
        )

    starting_stack = (
        validate_starting_stack(
            starting_stack
        )
    )

    normalized_levels = (
        validate_blind_levels(
            blind_levels
        )
    )

    tournament.structure.starting_stack = (
        starting_stack
    )

    for level in list(
        tournament.structure.blind_levels
    ):
        db.session.delete(
            level
        )

    db.session.flush()

    for position, (
        small_blind,
        big_blind,
        duration_minutes,
    ) in enumerate(
        normalized_levels,
        start=1,
    ):
        tournament.structure.blind_levels.append(
            BlindLevel(
                position=position,
                small_blind=small_blind,
                big_blind=big_blind,
                duration_seconds=(
                    duration_minutes
                    * 60
                ),
            )
        )

    if normalized_levels:
        tournament.structure.level_duration_minutes = (
            normalized_levels[0][2]
        )

    total_minutes = sum(
        level[2]
        for level in normalized_levels
    )

    tournament.structure.estimated_duration_min_minutes = (
        round(
            total_minutes
            * 0.85
        )
    )

    tournament.structure.estimated_duration_max_minutes = (
        round(
            total_minutes
            * 1.15
        )
    )


def save_manual_setup(
    *,
    tournament: Tournament,
    starting_stack: int,
    payouts: Sequence[int],
    blind_levels: Sequence[
        tuple[int, int, int]
    ],
) -> None:
    update_payouts(
        tournament=tournament,
        payouts=payouts,
    )

    update_structure(
        tournament=tournament,
        starting_stack=starting_stack,
        blind_levels=blind_levels,
    )

    tournament.status = "DRAFT"

    db.session.commit()


def mark_tournament_ready(
    tournament: Tournament,
) -> None:
    if tournament.structure is None:
        raise SetupError(
            "Turneringsstrukturen saknas."
        )

    validate_payouts(
        tournament=tournament,
        payouts=[
            prize.amount
            for prize in tournament.prizes
        ],
    )

    validate_starting_stack(
        tournament.structure.starting_stack
    )

    validate_blind_levels(
        [
            (
                level.small_blind,
                level.big_blind,
                level.duration_minutes,
            )
            for level in (
                tournament.structure.blind_levels
            )
        ]
    )

    tournament.status = "READY"

    db.session.commit()