from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from app.extensions import db
from app.models import AppMeta, Tournament, TournamentEvent, TournamentPlayer


class BuyinUndoError(ValueError):
    pass


def undo_key(tournament: Tournament) -> str:
    return f"buyin_undo:{tournament.id}"


def get_history(tournament: Tournament) -> tuple[AppMeta | None, list[dict]]:
    marker = db.session.scalar(select(AppMeta).where(AppMeta.key == undo_key(tournament)))
    return marker, json.loads(marker.value) if marker else []


def capture_buyin_state(tournament: Tournament) -> dict:
    """Capture financial state, excluding the running clock and event log."""
    result = tournament.result
    completion = None
    if tournament.status == "COMPLETED" and result is not None:
        completion = {
            "winner_entry_id": result.winner_entry_id,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "duration_seconds": result.duration_seconds,
            "winner_retained_bounty": result.winner_retained_bounty,
            "status_before_completion": result.status_before_completion,
        }
    return {
        "buy_in": tournament.buy_in,
        "bounty_enabled": tournament.bounty_enabled,
        "bounty_amount": tournament.bounty_amount,
        "starting_stack": tournament.structure.starting_stack if tournament.structure else None,
        "completion": completion,
        "completed_runtime": (
            {"current_level_position": tournament.runtime.current_level_position,
             "remaining_seconds_when_paused": tournament.runtime.remaining_seconds_when_paused}
            if completion is not None and tournament.runtime is not None else None
        ),
        "entries": [
            {"id": entry.id, "player_id": entry.player_id, "status": entry.status,
             "buy_in_count": entry.buy_in_count, "elimination_count": entry.elimination_count,
             "placement": entry.placement, "prize_winnings": entry.prize_winnings,
             "bounty_winnings": entry.bounty_winnings}
            for entry in sorted(tournament.players, key=lambda entry: entry.id)
        ],
        "prizes": [[prize.id, prize.place, prize.amount]
                   for prize in sorted(tournament.prizes, key=lambda prize: prize.place)],
        "bounties": sorted(
            [[bounty.winner_entry_id, bounty.eliminated_entry_id,
              bounty.elimination_number, bounty.amount] for bounty in tournament.bounties]
        ),
    }


def record_buyin(tournament: Tournament, before: dict, entry: TournamentPlayer, kind: str) -> None:
    """Persist undo history in the existing metadata table, in the buy-in transaction."""
    db.session.flush()
    marker, history = get_history(tournament)
    history.append({
        "id": uuid4().hex, "entry_id": entry.id, "name": entry.player.name,
        "kind": kind, "amount": tournament.buy_in,
        "before": before, "after": capture_buyin_state(tournament),
    })
    if marker is None:
        marker = AppMeta(key=undo_key(tournament))
        db.session.add(marker)
    marker.value = json.dumps(history, ensure_ascii=False)


def undo_buyin_state(tournament: Tournament) -> dict | None:
    _, history = get_history(tournament)
    if not history:
        return None
    action = history[-1]
    reason = None
    if tournament.status not in ("READY", "RUNNING", "PAUSED"):
        reason = "Inköp kan bara ångras i en redo, pågående eller pausad turnering."
    elif capture_buyin_state(tournament) != action["after"]:
        reason = "Ångra senare utslagningar eller andra ändringar först."
    return {"id": action["id"], "name": action["name"], "kind": action["kind"],
            "amount": action["amount"], "enabled": reason is None, "reason": reason}


def undo_last_buyin(tournament: Tournament, *, action_id: str) -> None:
    marker, history = get_history(tournament)
    if not history:
        raise BuyinUndoError("Det finns inget inköp att ångra.")
    action = history[-1]
    if action_id != action["id"]:
        raise BuyinUndoError("Inköpen har ändrats. Uppdatera sidan och försök igen.")
    state = undo_buyin_state(tournament)
    if not state["enabled"]:
        raise BuyinUndoError(state["reason"])

    before = action["before"]
    previous_entries = {entry["id"]: entry for entry in before["entries"]}
    for entry in list(tournament.players):
        if entry.id not in previous_entries:
            tournament.players.remove(entry)
            continue
        for field, value in previous_entries[entry.id].items():
            if field not in ("id", "player_id"):
                setattr(entry, field, value)
    prizes = {prize_id: amount for prize_id, _, amount in before["prizes"]}
    for prize in tournament.prizes:
        prize.amount = prizes[prize.id]

    # A re-entry can reopen a finished tournament. Undo restores its original
    # result (including the winner's retained bounty), rather than completing anew.
    completion = before["completion"]
    if completion is not None:
        tournament.status = "COMPLETED"
        result = tournament.result
        for field, value in completion.items():
            if field == "completed_at" and value is not None:
                value = datetime.fromisoformat(value)
            setattr(result, field, value)
        if tournament.runtime is not None:
            tournament.runtime.timer_started_at = None
            for field, value in (before["completed_runtime"] or {}).items():
                setattr(tournament.runtime, field, value)

    db.session.add(TournamentEvent(
        tournament=tournament, event_type="BUYIN_UNDONE",
        message=f"Inköp för {action['name']} ångrades ({action['amount']} kr)",
    ))
    history.pop()
    if history:
        marker.value = json.dumps(history, ensure_ascii=False)
    else:
        db.session.delete(marker)
    db.session.commit()


def clear_buyin_history(tournament: Tournament) -> None:
    marker, _ = get_history(tournament)
    if marker is not None:
        db.session.delete(marker)
