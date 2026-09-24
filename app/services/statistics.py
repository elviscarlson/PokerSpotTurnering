from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Player,
    Tournament,
    TournamentPlayer,
)


@dataclass(frozen=True)
class PlayerStatistics:
    player: Player
    tournaments: int
    wins: int
    itm_finishes: int
    itm_percentage: float
    total_buyins: int
    prize_winnings: int
    bounty_winnings: int
    bounty_count: int
    total_winnings: int
    net_result: int


@dataclass(frozen=True)
class DashboardStatistics:
    completed_tournaments: int
    total_players: int
    latest_tournament: Tournament | None
    total_prize_money: int
    total_bounty_money: int
    total_money_played: int


def completed_entries(
    player: Player,
) -> list[TournamentPlayer]:
    return [
        entry
        for entry in player.tournament_entries
        if (
            entry.tournament.status
            == "COMPLETED"
            and entry.placement
            is not None
        )
    ]


def entry_bounty_count(
    entry: TournamentPlayer,
) -> int:
    count = len(
        entry.bounties_won
    )

    tournament = (
        entry.tournament
    )

    if (
        tournament.status
        == "COMPLETED"
        and tournament.result
        is not None
        and tournament.result.winner_entry_id
        == entry.id
        and tournament.result.winner_retained_bounty
        > 0
    ):
        count += 1

    return count


def calculate_player_statistics(
    player: Player,
) -> PlayerStatistics:
    entries = completed_entries(
        player
    )

    tournaments = len(
        entries
    )

    wins = sum(
        1
        for entry in entries
        if entry.placement == 1
    )

    itm_finishes = sum(
        1
        for entry in entries
        if entry.prize_winnings > 0
    )

    total_buyins = sum(
        entry.tournament.buy_in
        for entry in entries
    )

    prize_winnings = sum(
        entry.prize_winnings
        for entry in entries
    )

    bounty_winnings = sum(
        entry.bounty_winnings
        for entry in entries
    )

    bounty_count = sum(
        entry_bounty_count(
            entry
        )
        for entry in entries
    )

    total_winnings = (
        prize_winnings
        + bounty_winnings
    )

    net_result = (
        total_winnings
        - total_buyins
    )

    itm_percentage = (
        (
            itm_finishes
            / tournaments
        )
        * 100
        if tournaments
        else 0.0
    )

    return PlayerStatistics(
        player=player,
        tournaments=tournaments,
        wins=wins,
        itm_finishes=itm_finishes,
        itm_percentage=(
            itm_percentage
        ),
        total_buyins=(
            total_buyins
        ),
        prize_winnings=(
            prize_winnings
        ),
        bounty_winnings=(
            bounty_winnings
        ),
        bounty_count=(
            bounty_count
        ),
        total_winnings=(
            total_winnings
        ),
        net_result=(
            net_result
        ),
    )


def all_player_statistics() -> list[
    PlayerStatistics
]:
    players = db.session.scalars(
        select(Player).order_by(
            Player.name.asc()
        )
    ).all()

    return [
        calculate_player_statistics(
            player
        )
        for player in players
    ]


def winnings_leaderboard(
    *,
    limit: int = 5,
) -> list[PlayerStatistics]:
    statistics = (
        all_player_statistics()
    )

    eligible = [
        stat
        for stat in statistics
        if stat.tournaments > 0
    ]

    return sorted(
        eligible,
        key=lambda stat: (
            stat.total_winnings,
            stat.wins,
            stat.prize_winnings,
            stat.player.name.casefold(),
        ),
        reverse=True,
    )[:limit]


def wins_leaderboard(
    *,
    limit: int = 5,
) -> list[PlayerStatistics]:
    statistics = (
        all_player_statistics()
    )

    eligible = [
        stat
        for stat in statistics
        if stat.tournaments > 0
    ]

    return sorted(
        eligible,
        key=lambda stat: (
            stat.wins,
            stat.total_winnings,
            stat.player.name.casefold(),
        ),
        reverse=True,
    )[:limit]


def bounty_leaderboard(
    *,
    limit: int = 5,
) -> list[PlayerStatistics]:
    statistics = (
        all_player_statistics()
    )

    eligible = [
        stat
        for stat in statistics
        if stat.tournaments > 0
    ]

    return sorted(
        eligible,
        key=lambda stat: (
            stat.bounty_count,
            stat.bounty_winnings,
            stat.player.name.casefold(),
        ),
        reverse=True,
    )[:limit]


def calculate_dashboard_statistics(
) -> DashboardStatistics:
    completed = db.session.scalars(
        select(Tournament)
        .where(
            Tournament.status
            == "COMPLETED"
        )
    ).all()

    players = db.session.scalars(
        select(Player)
    ).all()

    latest_tournament = None

    if completed:
        latest_tournament = max(
            completed,
            key=lambda tournament: (
                (
                    tournament.result
                    .completed_at
                )
                if (
                    tournament.result
                    is not None
                    and tournament.result
                    .completed_at
                    is not None
                )
                else tournament.created_at
            ),
        )

    total_prize_money = sum(
        tournament.total_prizes
        for tournament in completed
    )

    total_bounty_money = sum(
        tournament.total_bounty_winnings
        for tournament in completed
    )

    total_money_played = sum(
        tournament.total_buyins
        for tournament in completed
    )

    return DashboardStatistics(
        completed_tournaments=len(
            completed
        ),
        total_players=len(
            players
        ),
        latest_tournament=(
            latest_tournament
        ),
        total_prize_money=(
            total_prize_money
        ),
        total_bounty_money=(
            total_bounty_money
        ),
        total_money_played=(
            total_money_played
        ),
    )