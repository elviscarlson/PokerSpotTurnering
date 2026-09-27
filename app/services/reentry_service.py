from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    Prize,
    Tournament,
    TournamentEvent,
    TournamentPlayer,
)


class ReentryError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def get_entry(
    tournament: Tournament,
    entry_id: int,
) -> TournamentPlayer:
    entry = db.session.get(
        TournamentPlayer,
        entry_id,
    )

    if (
        entry is None
        or entry.tournament_id
        != tournament.id
    ):
        raise ReentryError(
            "Spelaren finns inte i turneringen."
        )

    return entry


def add_event(
    *,
    tournament: Tournament,
    event_type: str,
    message: str,
) -> TournamentEvent:
    event = TournamentEvent(
        tournament=tournament,
        event_type=event_type,
        message=message,
    )

    db.session.add(
        event
    )

    return event


def calculate_regular_pool(
    tournament: Tournament,
) -> int:
    return (
        tournament.total_buyins
        - tournament.bounty_pool
    )


def round_payouts_exactly(
    *,
    prize_pool: int,
    existing_prizes: list[Prize],
) -> list[int]:
    """
    Scale the existing payout structure to the new prize pool.

    The number of paid positions stays unchanged after a re-entry.

    Existing prize proportions are preserved as closely as possible,
    while ensuring:

        sum(new_payouts) == prize_pool
    """

    if prize_pool < 0:
        raise ReentryError(
            "Prispotten kan inte vara negativ."
        )

    if not existing_prizes:
        raise ReentryError(
            "Turneringen saknar payoutstruktur."
        )

    ordered_prizes = sorted(
        existing_prizes,
        key=lambda prize: prize.place,
    )

    previous_total = sum(
        prize.amount
        for prize in ordered_prizes
    )

    if previous_total <= 0:
        raise ReentryError(
            "Den befintliga payoutstrukturen är ogiltig."
        )

    if prize_pool < 500:
        rounding_increment = 10
    elif prize_pool < 2_000:
        rounding_increment = 50
    else:
        rounding_increment = 100

    weights = [
        prize.amount
        / previous_total
        for prize in ordered_prizes
    ]

    payouts = []

    for weight in weights:
        raw_amount = (
            prize_pool
            * weight
        )

        rounded_amount = (
            int(
                raw_amount
                // rounding_increment
            )
            * rounding_increment
        )

        payouts.append(
            rounded_amount
        )

    difference = (
        prize_pool
        - sum(payouts)
    )

    payouts[0] += (
        difference
    )

    if sum(payouts) != prize_pool:
        raise ReentryError(
            "Payoutstrukturen kunde inte balanseras."
        )

    if any(
        amount < 0
        for amount in payouts
    ):
        raise ReentryError(
            "Payoutstrukturen innehåller negativa belopp."
        )

    return payouts


def recalculate_prizes(
    tournament: Tournament,
) -> None:
    """
    Recalculate prize amounts after a re-entry.

    Re-entry increases the money in the tournament, but does not
    increase the number of paid positions because the number of
    unique players has not changed.
    """

    prize_pool = (
        calculate_regular_pool(
            tournament
        )
    )

    prizes = sorted(
        tournament.prizes,
        key=lambda prize: prize.place,
    )

    payouts = (
        round_payouts_exactly(
            prize_pool=prize_pool,
            existing_prizes=prizes,
        )
    )

    for (
        prize,
        amount,
    ) in zip(
        prizes,
        payouts,
        strict=True,
    ):
        prize.amount = amount


def shift_eliminated_placements_for_reentry(
    *,
    tournament: Tournament,
    reentering_entry: TournamentPlayer,
) -> None:
    """
    Remove the re-entering player's old final placement from the
    current ordering.

    Example:

        Philip = 5th
        Hugo   = 4th

    If Philip re-enters:

        Hugo becomes 5th
        Philip becomes ACTIVE

    The next elimination will then correctly receive 4th place.
    """

    old_placement = (
        reentering_entry.placement
    )

    if old_placement is None:
        return

    for entry in tournament.players:
        if (
            entry.id
            == reentering_entry.id
        ):
            continue

        if (
            entry.status
            != "ELIMINATED"
        ):
            continue

        if entry.placement is None:
            continue

        if (
            entry.placement
            < old_placement
        ):
            entry.placement += 1


def clear_prize_if_needed(
    entry: TournamentPlayer,
) -> None:
    """
    A player that re-enters no longer has a final placement,
    therefore any prize temporarily attached to that placement
    must be removed.
    """

    entry.prize_winnings = 0


def reopen_completed_tournament_for_reentry(
    tournament: Tournament,
) -> None:
    """
    Reopen a tournament that was automatically completed after
    reaching heads-up and then receives a re-entry.

    The previously declared winner is no longer the final winner.

    Important:
    bounty money that was genuinely won remains paid.
    """

    if tournament.status != "COMPLETED":
        return

    result = tournament.result

    if result is None:
        raise ReentryError(
            "Turneringen är markerad som avslutad men saknar resultatdata."
        )

    winner = tournament.winner

    if winner is not None:
        winner.placement = None
        winner.prize_winnings = 0

        retained_bounty = (
            result.winner_retained_bounty
            or 0
        )

        if retained_bounty > 0:
            winner.bounty_winnings = max(
                0,
                winner.bounty_winnings
                - retained_bounty,
            )

    result.winner_entry = None
    result.completed_at = None
    result.duration_seconds = None
    result.winner_retained_bounty = 0

    previous_status = (
        result.status_before_completion
    )

    if previous_status not in (
        "RUNNING",
        "PAUSED",
    ):
        previous_status = "PAUSED"

    tournament.status = (
        previous_status
    )

    result.status_before_completion = None

    runtime = tournament.runtime

    if runtime is not None:
        if tournament.status == "RUNNING":
            runtime.timer_started_at = (
                utc_now()
            )
        else:
            runtime.timer_started_at = None

    add_event(
        tournament=tournament,
        event_type="TOURNAMENT_REOPENED",
        message=(
            "Tournament reopened after re-entry"
        ),
    )


def validate_reentry(
    *,
    tournament: Tournament,
    entry: TournamentPlayer,
) -> None:
    if tournament.status not in (
        "RUNNING",
        "PAUSED",
        "COMPLETED",
    ):
        raise ReentryError(
            "Re-entry är endast tillåten efter att turneringen har startat."
        )

    if entry.status != "ELIMINATED":
        raise ReentryError(
            "Endast en eliminerad spelare kan köpa in igen."
        )

    if entry.placement is None:
        raise ReentryError(
            "Den eliminerade spelaren saknar placering."
        )

    if tournament.buy_in <= 0:
        raise ReentryError(
            "Turneringen har ett ogiltigt buy-in."
        )

    if (
        tournament.bounty_enabled
        and tournament.bounty_amount
        >= tournament.buy_in
    ):
        raise ReentryError(
            "Bountybeloppet måste vara mindre än buy-in."
        )


def register_reentry(
    *,
    tournament: Tournament,
    entry_id: int,
) -> TournamentPlayer:
    """
    Register one additional full buy-in for an eliminated player.

    Effects:
    - buy_in_count + 1
    - player becomes ACTIVE
    - old placement is removed
    - previously earned bounty winnings remain
    - previously awarded bounty on this bust remains
    - prize pool increases
    - bounty pool increases when bounty is enabled
    - payouts are recalculated
    - tournament can be reopened if it had just completed
    """

    entry = get_entry(
        tournament,
        entry_id,
    )

    validate_reentry(
        tournament=tournament,
        entry=entry,
    )

    old_buy_in_count = (
        entry.buy_in_count
    )

    old_total_buyins = (
        tournament.total_buyins
    )

    old_regular_pool = (
        tournament.regular_prize_pool
    )

    old_bounty_pool = (
        tournament.bounty_pool
    )

    if tournament.status == "COMPLETED":
        reopen_completed_tournament_for_reentry(
            tournament
        )

    shift_eliminated_placements_for_reentry(
        tournament=tournament,
        reentering_entry=entry,
    )

    clear_prize_if_needed(
        entry
    )

    entry.buy_in_count += 1

    entry.status = "ACTIVE"

    entry.placement = None

    db.session.flush()

    expected_total_buyins = (
        old_total_buyins
        + tournament.buy_in
    )

    if (
        tournament.total_buyins
        != expected_total_buyins
    ):
        db.session.rollback()

        raise ReentryError(
            "Total buy-in uppdaterades inte korrekt."
        )

    expected_regular_increase = (
        tournament.buy_in
        - (
            tournament.bounty_amount
            if tournament.bounty_enabled
            else 0
        )
    )

    expected_regular_pool = (
        old_regular_pool
        + expected_regular_increase
    )

    if (
        tournament.regular_prize_pool
        != expected_regular_pool
    ):
        db.session.rollback()

        raise ReentryError(
            "Prispotten uppdaterades inte korrekt."
        )

    if tournament.bounty_enabled:
        expected_bounty_pool = (
            old_bounty_pool
            + tournament.bounty_amount
        )

        if (
            tournament.bounty_pool
            != expected_bounty_pool
        ):
            db.session.rollback()

            raise ReentryError(
                "Bounty-potten uppdaterades inte korrekt."
            )

    recalculate_prizes(
        tournament
    )

    if (
        tournament.total_prizes
        != tournament.regular_prize_pool
    ):
        db.session.rollback()

        raise ReentryError(
            "Payouts motsvarar inte den nya prispotten."
        )

    add_event(
        tournament=tournament,
        event_type="PLAYER_REENTRY",
        message=(
            f"{entry.player.name} re-entered "
            f"({old_buy_in_count + 1} buy-ins)"
        ),
    )

    db.session.commit()

    return entry