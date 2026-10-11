import pytest
from sqlalchemy import func, select, text

from app.extensions import db
from app.models import AppMeta, Player, Tournament
from app.services.buyin_undo import (
    BuyinUndoError, capture_buyin_state, undo_buyin_state, undo_last_buyin,
)
from app.services.clock_service import pause_clock, start_clock
from app.services.late_registration import register_late_player
from app.services.player_elimination import eliminate_player, restore_last_elimination
from app.services.reentry_service import register_reentry
from app.services.statistics import calculate_player_statistics
from tests.test_late_registration import build_game


def undo(tournament):
    state = undo_buyin_state(tournament)
    assert state["enabled"]
    undo_last_buyin(tournament, action_id=state["id"])


@pytest.mark.parametrize("bounty", [True, False])
@pytest.mark.parametrize("status", ["READY", "RUNNING", "PAUSED"])
def test_late_buyin_undo_restores_exact_state(app, bounty, status):
    with app.app_context():
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        tournament, reserve = build_game(bounty, status)
        before = capture_buyin_state(tournament)
        runtime = tournament.runtime
        clock = (runtime.timer_started_at, runtime.remaining_seconds_when_paused) if runtime else None
        register_late_player(tournament=tournament, player_id=reserve.id)
        undo(tournament)
        assert capture_buyin_state(tournament) == before
        assert tournament.total_entries == 4
        assert tournament.total_buyins == 1200
        assert tournament.total_prizes == tournament.regular_prize_pool
        assert tournament.structure.total_chips == 4 * tournament.structure.starting_stack
        assert tournament.status == status
        assert ((runtime.timer_started_at, runtime.remaining_seconds_when_paused) if runtime else None) == clock
        assert undo_buyin_state(tournament) is None
        assert db.session.get(Player, reserve.id) is not None


def test_undo_new_player_keeps_player_and_survives_new_session(app):
    with app.app_context():
        tournament, _ = build_game()
        tournament_id = tournament.id
        before = capture_buyin_state(tournament)
        entry = register_late_player(tournament=tournament, name="Sara")
        player_id = entry.player_id
        db.session.remove()
        tournament = db.session.get(Tournament, tournament_id)
        undo(tournament)
        assert capture_buyin_state(tournament) == before
        assert db.session.get(Player, player_id).name == "Sara"


@pytest.mark.parametrize("bounty", [True, False])
def test_reentry_undo_restores_placements_prizes_and_bounties(app, bounty):
    with app.app_context():
        tournament, _ = build_game(bounty)
        winner, hugo, leo, elias = tournament.players
        for eliminated in (elias, leo):
            eliminate_player(tournament=tournament, entry_id=eliminated.id,
                             eliminated_by_entry_id=winner.id if bounty else None)
        before = capture_buyin_state(tournament)
        register_reentry(tournament=tournament, entry_id=elias.id)
        assert elias.buy_in_count == 2
        assert leo.placement == 4
        undo(tournament)
        assert capture_buyin_state(tournament) == before
        assert elias.status == "ELIMINATED" and elias.placement == 4
        assert leo.placement == 3
        assert winner.bounty_winnings == (100 if bounty else 0)


def test_multiple_buyins_can_be_undone_in_reverse_order(app):
    with app.app_context():
        tournament, reserve = build_game()
        before = capture_buyin_state(tournament)
        register_late_player(tournament=tournament, player_id=reserve.id)
        first_state = capture_buyin_state(tournament)
        first_id = undo_buyin_state(tournament)["id"]
        register_late_player(tournament=tournament, name="Sara")
        with pytest.raises(BuyinUndoError, match="Inköpen har ändrats"):
            undo_last_buyin(tournament, action_id=first_id)
        undo(tournament)
        assert capture_buyin_state(tournament) == first_state
        undo(tournament)
        assert capture_buyin_state(tournament) == before


def test_later_elimination_must_be_restored_first(app):
    with app.app_context():
        tournament, reserve = build_game()
        before = capture_buyin_state(tournament)
        late = register_late_player(tournament=tournament, player_id=reserve.id)
        winner = tournament.players[0]
        eliminate_player(tournament=tournament, entry_id=late.id,
                         eliminated_by_entry_id=winner.id)
        action_id = undo_buyin_state(tournament)["id"]
        after_elimination = capture_buyin_state(tournament)
        assert not undo_buyin_state(tournament)["enabled"]
        with pytest.raises(BuyinUndoError, match="Ångra senare"):
            undo_last_buyin(tournament, action_id=action_id)
        assert capture_buyin_state(tournament) == after_elimination
        restore_last_elimination(tournament=tournament, entry_id=late.id)
        undo(tournament)
        assert capture_buyin_state(tournament) == before


@pytest.mark.parametrize("status", ["RUNNING", "PAUSED"])
def test_undo_reentry_reinstates_original_completed_result(app, status):
    with app.app_context():
        tournament, _ = build_game(status=status)
        winner = tournament.players[0]
        for entry in tournament.players[1:]:
            eliminate_player(tournament=tournament, entry_id=entry.id,
                             eliminated_by_entry_id=winner.id)
        before = capture_buyin_state(tournament)
        statistics = calculate_player_statistics(winner.player)
        runner_up = tournament.players[-1]
        register_reentry(tournament=tournament, entry_id=runner_up.id)
        assert tournament.status == status
        undo(tournament)
        assert tournament.status == "COMPLETED"
        assert capture_buyin_state(tournament) == before
        assert calculate_player_statistics(winner.player) == statistics
        assert sum(entry.total_winnings for entry in tournament.players) == tournament.total_buyins
        assert tournament.runtime.timer_started_at is None


def test_clock_start_and_pause_do_not_block_undo(app):
    with app.app_context():
        tournament, reserve = build_game(status="READY")
        register_late_player(tournament=tournament, player_id=reserve.id)
        start_clock(tournament)
        pause_clock(tournament)
        undo(tournament)
        assert tournament.status == "PAUSED"
        assert tournament.active_player_count == 4


def test_existing_buyins_without_history_are_not_guessed(app):
    with app.app_context():
        tournament, _ = build_game()
        assert undo_buyin_state(tournament) is None
        with pytest.raises(BuyinUndoError, match="inget inköp"):
            undo_last_buyin(tournament, action_id="unknown")


@pytest.mark.parametrize("payload", [None, [], {"action_id": 123}, {"action_id": "stale"}])
def test_invalid_undo_request_does_not_change_data(client, app, payload):
    with app.app_context():
        tournament, reserve = build_game()
        register_late_player(tournament=tournament, player_id=reserve.id)
        tournament_id = tournament.id
        before = capture_buyin_state(tournament)
    response = client.post(f"/api/tournaments/{tournament_id}/undo-buyin", json=payload)
    assert response.status_code == 400
    with app.app_context():
        assert capture_buyin_state(db.session.get(Tournament, tournament_id)) == before


def test_undo_endpoint_and_duplicate_request(client, app):
    with app.app_context():
        tournament, reserve = build_game()
        register_late_player(tournament=tournament, player_id=reserve.id)
        tournament_id = tournament.id
    state = client.get(f"/api/tournaments/{tournament_id}/state").get_json()
    assert state["undo_buyin"]["name"] == "Anton"
    url = f"/api/tournaments/{tournament_id}/undo-buyin"
    response = client.post(url, json={"action_id": state["undo_buyin"]["id"]})
    assert response.status_code == 200
    assert response.get_json()["players_total"] == 4
    assert response.get_json()["undo_buyin"] is None
    assert client.post(url, json={"action_id": state["undo_buyin"]["id"]}).status_code == 400


def test_delete_tournament_cleans_up_buyin_history(client, app):
    with app.app_context():
        tournament, reserve = build_game()
        register_late_player(tournament=tournament, player_id=reserve.id)
        tournament_id = tournament.id
    url = f"/tournaments/{tournament_id}/delete"
    client.get(url)
    with client.session_transaction() as session:
        token = session["tournament_delete_token"]
    assert client.post(url, data={"delete_token": token}).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(func.count(AppMeta.id)).where(
            AppMeta.key == f"buyin_undo:{tournament_id}")) == 0
