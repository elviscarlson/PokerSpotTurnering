from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models import Player, Tournament, TournamentEvent, TournamentPlayer
from app.services.player_service import player_name_key, validate_player_name
from app.services.reentry_service import recalculate_prizes
from app.services.buyin_undo import capture_buyin_state, record_buyin


class LateRegistrationError(ValueError):
    pass


def available_registration_players(tournament: Tournament) -> list[Player]:
    """Read eligible players from the current register, including new arrivals."""
    registered_ids = select(TournamentPlayer.player_id).where(
        TournamentPlayer.tournament_id == tournament.id
    )
    return db.session.scalars(
        select(Player).where(
            Player.is_active.is_(True),
            Player.id.not_in(registered_ids),
        ).order_by(Player.name.asc(), Player.id.asc())
    ).all()


def register_late_player(
    *,
    tournament: Tournament,
    player_id: int | None = None,
    name: str = "",
) -> TournamentPlayer:
    """Add a first buy-in without changing the clock or paid places.

    Eliminated players move down one place as the field grows. Their
    prize winnings are refreshed against the increased prize pool.
    A new player and their entry are saved in the same transaction.
    """
    if tournament.status not in ("READY", "RUNNING", "PAUSED"):
        raise LateRegistrationError(
            "Spelare kan bara läggas till i en redo, pågående eller pausad turnering."
        )
    if tournament.structure is None or not tournament.prizes:
        raise LateRegistrationError("Turneringsstrukturen eller priserna saknas.")
    if (player_id is not None) == bool(name.strip()):
        raise LateRegistrationError("Välj en befintlig spelare eller ange ett nytt namn.")

    if player_id is not None:
        player = db.session.get(Player, player_id)
        if player is None or not player.is_active:
            raise LateRegistrationError("Välj en aktiv spelare som finns i spelarlistan.")
        if any(entry.player_id == player_id for entry in tournament.players):
            raise LateRegistrationError(
                "Spelaren finns redan i turneringen. Använd Re-entry för återinköp."
            )
    else:
        cleaned_name = validate_player_name(name)
        name_key = player_name_key(cleaned_name)
        if db.session.scalar(select(Player).where(Player.name_key == name_key)):
            raise LateRegistrationError(
                "Spelarnamnet finns redan. Välj spelaren i listan i stället."
            )
        player = Player(name=cleaned_name, name_key=name_key)
        db.session.add(player)

    before = capture_buyin_state(tournament)
    entry = TournamentPlayer(player=player, status="ACTIVE", buy_in_count=1)
    tournament.players.append(entry)

    for eliminated in tournament.players:
        if eliminated.status == "ELIMINATED" and eliminated.placement is not None:
            eliminated.placement += 1

    recalculate_prizes(tournament)
    prizes = {prize.place: prize.amount for prize in tournament.prizes}
    for eliminated in tournament.players:
        if eliminated.status == "ELIMINATED":
            eliminated.prize_winnings = prizes.get(eliminated.placement, 0)

    db.session.add(TournamentEvent(
        tournament=tournament,
        event_type="PLAYER_REGISTERED",
        message=f"{player.name} joined the tournament ({tournament.buy_in} kr)",
    ))
    record_buyin(tournament, before, entry, "LATE_REGISTRATION")
    db.session.commit()
    return entry
