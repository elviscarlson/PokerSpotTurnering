from datetime import date
import random

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.extensions import db
from app.models import AppMeta, CashGame, CashGameBuyIn, Player, Tournament
from app.services import cashgame as cash
from app.services.player_service import create_player


def players():
    return [create_player(name) for name in ("Leo", "Elvis", "Hugo", "Erik")]


def game_with_result(participants):
    game = cash.create_game("Fredagscash", date(2026, 10, 16), participants, 20_000)
    db.session.commit()
    cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, [35_000, 25_000, 15_000, 5_000])})
    cash.complete_game(game)
    db.session.commit()
    return game


@pytest.mark.parametrize("value,expected", [("200", 20000), ("12,50", 1250), ("0.01", 1), ("1 200,05", 120005), ("1000000", 100000000)])
def test_money_preserves_exact_ore(value, expected):
    assert cash.parse_money(value) == expected


@pytest.mark.parametrize("value", ["", "-1", "NaN", "Infinity", "1e3", "12,345", "2.5.0", "1000001", "0"])
def test_invalid_buy_in_amounts_are_rejected(value):
    with pytest.raises(cash.CashGameError):
        cash.parse_money(value)


def test_cash_out_can_be_explicit_zero_but_not_missing():
    assert cash.parse_money("0", allow_zero=True) == 0
    with pytest.raises(cash.CashGameError):
        cash.parse_money("", allow_zero=True)


def test_late_buy_in_and_undo_restore_totals_and_require_new_cash_out(app):
    with app.app_context():
        people = players()
        game = cash.create_game("Test", date.today(), people[:2], 20_000)
        db.session.commit()
        first = game.entries[0]
        cash.save_cash_outs(game, {entry.id: 20_000 for entry in game.entries})
        cash.add_buy_in(game, people[0], 10_050)
        db.session.commit()
        assert game.total_buy_ins == 50_050
        assert first.cash_out_ore is None
        cash.undo_buy_in(game, first.buy_ins[-1].id)
        db.session.commit()
        assert game.total_buy_ins == 40_000
        assert first.buy_in_count == 1
        cash.add_buy_in(game, people[2], 25_000)
        db.session.commit()
        assert len(game.entries) == 3
        assert game.total_buy_ins == 65_000
        with pytest.raises(cash.CashGameError):
            cash.undo_buy_in(game, first.buy_ins[-1].id)


def test_all_cash_outs_and_at_least_one_winner_are_needed_to_resolve_difference(app):
    with app.app_context():
        game = cash.create_game("Test", date.today(), players(), 20_000)
        db.session.commit()
        with pytest.raises(cash.CashGameError, match="alla spelare"):
            cash.complete_game(game)
        cash.save_cash_outs(game, {entry.id: 0 for entry in game.entries})
        with pytest.raises(cash.CashGameError, match="ingen spelare ligger plus"):
            cash.complete_game(game)
        assert game.status == "OPEN"
        cash.save_cash_outs(game, {entry.id: 20_000 for entry in game.entries})
        cash.complete_game(game)
        assert cash.settlement_plan(game) == []


def test_negative_cash_out_and_changed_participant_list_rejected_atomically(app):
    with app.app_context():
        game = cash.create_game("Test", date.today(), players(), 20_000)
        db.session.commit()
        amounts = {entry.id: 20_000 for entry in game.entries}
        amounts[game.entries[-1].id] = -1
        with pytest.raises(cash.CashGameError):
            cash.save_cash_outs(game, amounts)
        assert all(entry.cash_out_ore is None for entry in game.entries)
        with pytest.raises(cash.CashGameError):
            cash.save_cash_outs(game, {game.entries[0].id: 20_000})


def test_partial_swish_and_undo_update_remaining_debts_without_changing_results(app):
    with app.app_context():
        people = players()
        game = game_with_result(people)
        plan = cash.settlement_plan(game)
        assert [(t.payer.name, t.receiver.name, t.amount_ore) for t in plan] == [("Erik", "Leo", 15_000), ("Hugo", "Elvis", 5_000)]
        cash.record_transfer(game, people[3].id, people[0].id, 10_000)
        db.session.commit()
        assert cash.remaining_balances(game) == {people[0].id: 5_000, people[1].id: 5_000, people[2].id: -5_000, people[3].id: -5_000}
        assert sum(t.amount_ore for t in cash.settlement_plan(game)) == 10_000
        assert cash.summaries([game])[0]["net"] == 15_000
        with pytest.raises(cash.CashGameError):
            cash.reopen_game(game)
        with pytest.raises(cash.CashGameError):
            cash.record_transfer(game, people[3].id, people[0].id, 5_001)
        cash.undo_transfer(game, game.transfers[0].id)
        assert sum(t.amount_ore for t in cash.settlement_plan(game)) == 20_000
        cash.reopen_game(game)
        assert game.status == "OPEN"


def test_settlement_conserves_every_players_balance_to_the_ore(app):
    with app.app_context():
        people = players()
        rng = random.Random(42)
        for index in range(30):
            game = cash.create_game(f"Game {index}", date.today(), people, 10_001)
            db.session.commit()
            cuts = sorted([0, 40_004] + [rng.randrange(40_005) for _ in range(3)])
            payouts = [right - left for left, right in zip(cuts, cuts[1:])]
            cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, payouts)})
            cash.complete_game(game)
            balances = cash.remaining_balances(game)
            plan = cash.settlement_plan(game)
            for payment in plan:
                assert payment.amount_ore > 0
                assert balances[payment.payer.id] < 0 < balances[payment.receiver.id]
                balances[payment.payer.id] += payment.amount_ore
                balances[payment.receiver.id] -= payment.amount_ore
                cash.record_transfer(game, payment.payer.id, payment.receiver.id, payment.amount_ore)
            assert set(balances.values()) == {0}
            assert cash.settlement_plan(game) == []


def test_statistics_exclude_open_games_and_tournaments_and_use_chronological_dates(app):
    with app.app_context():
        people = players()
        later = game_with_result(people)
        earlier = game_with_result(people)
        earlier.played_on = date(2026, 10, 9)
        cash.create_game("Inte färdigt", date.today(), people, 99_900)
        db.session.add(Tournament(name="Separat turnering", tournament_date=date.today(), target_duration_minutes=60, buy_in=1000, status="COMPLETED"))
        db.session.commit()
        report = cash.player_report(people[0], cash.all_games())
        assert report["buy_ins"] == 40_000
        assert report["net"] == 30_000
        assert report["count"] == 2
        assert [item["game"].id for item in report["history"]] == [earlier.id, later.id]
        assert [point["value"] for point in report["series"]] == [0, 15_000, 30_000]


def token(client):
    client.get("/cashgame/new")
    with client.session_transaction() as state:
        return state["cashgame_csrf"]


def test_routes_create_buy_in_cash_out_complete_and_reject_duplicate_post(app, client):
    with app.app_context():
        people = players()
        ids = [p.id for p in people]
    csrf = token(client)
    response = client.post("/cashgame/new", data={"csrf_token": csrf, "name": "Fredag", "played_on": "2026-10-16", "buy_in": "200", "player_ids": ids})
    assert response.status_code == 302
    with app.app_context():
        game = db.session.scalar(select(CashGame))
        game_id, version = game.id, game.version
    payload = {"csrf_token": csrf, "version": version, "player_id": ids[0], "amount": "50,25"}
    client.post(f"/cashgame/{game_id}/buy-ins", data=payload)
    client.post(f"/cashgame/{game_id}/buy-ins", data=payload)
    with app.app_context():
        game = db.session.get(CashGame, game_id)
        assert game.total_buy_ins == 85_025
        assert game.version == version + 1
        amounts = {f"cash_out_{entry.id}": amount for entry, amount in zip(game.entries, ["400,25", "250", "150", "50"])}
        version = game.version
    client.post(f"/cashgame/{game_id}/cash-outs", data={"csrf_token": csrf, "version": version, **amounts})
    response = client.post(f"/cashgame/{game_id}/complete", data={"csrf_token": csrf, "version": version + 1}, follow_redirects=True)
    assert response.status_code == 200
    assert "Vem swishar vem?" in response.text
    assert "Swish-förslag är klara" in response.text
    assert client.get("/cashgame/?player_id=" + str(ids[0])).status_code == 200


def test_post_requires_csrf_and_unknown_game_returns_404(client):
    assert client.post("/cashgame/new", data={}).status_code == 400
    assert client.get("/cashgame/999").status_code == 404


@pytest.mark.parametrize("slug", cash.PROFILE_SLUGS)
def test_all_friend_pages_show_cashgame_and_allow_explicit_player_binding(app, client, slug):
    with app.app_context():
        people = players()
        game_with_result(people)
        target_id = people[0].id
    page = client.get(f"/{slug}")
    assert page.status_code == 200
    assert "Cashgame-resultat" in page.text
    with client.session_transaction() as state:
        csrf = state["cashgame_csrf"]
    response = client.post(f"/cashgame/profiles/{slug}", data={"csrf_token": csrf, "player_id": target_id}, follow_redirects=True)
    assert response.status_code == 200
    assert "+150 kr" in response.text
    assert "cashgame-results" in response.text


def test_ambiguous_first_names_require_explicit_profile_binding(app):
    with app.app_context():
        create_player("Leo Andersson")
        create_player("Leo Svensson")
        assert cash.profile_context("leo")["cashgame_player"] is None


def test_old_database_can_add_cashgame_tables_without_losing_players(app):
    with app.app_context():
        person = create_player("Bevara mig")
        player_id = person.id
        for table in reversed(db.metadata.sorted_tables):
            if table.name.startswith("cash_game"):
                table.drop(db.engine)
    result = app.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0
    with app.app_context():
        assert db.session.get(Player, player_id).name == "Bevara mig"
        assert cash.all_games() == []


@pytest.mark.parametrize("cash_outs,expected", [
    ([35_001, 25_000, 15_000, 5_000], [-1, 0, 0, 0]),
    ([34_999, 24_998, 15_000, 5_000], [2, 1, 0, 0]),
    ([20_001, 30_000, 19_000, 19_000], [-1, -8_000, 0, 0]),
])
def test_difference_is_shared_by_winners_exactly_and_never_turns_them_into_losers(app, cash_outs, expected):
    with app.app_context():
        people = players()
        game = cash.create_game("Med diff", date.today(), people, 20_000)
        db.session.commit()
        cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, cash_outs)})
        preview = cash.difference_adjustments(game)
        assert [preview.get(entry.id, 0) for entry in game.entries] == expected
        cash.complete_game(game)
        db.session.commit()
        assert [entry.cash_out_ore for entry in game.entries] == cash_outs
        assert [entry.cash_out_adjustment_ore for entry in game.entries] == expected
        assert sum(entry.net for entry in game.entries) == 0
        assert all(entry.net >= 0 for entry, raw in zip(game.entries, cash_outs) if raw > 20_000)
        assert sum(row["net"] for row in cash.summaries([game])) == 0
        assert sum(row["cash_outs"] for row in cash.summaries([game])) == game.total_buy_ins
        for payment in cash.settlement_plan(game):
            cash.record_transfer(game, payment.payer.id, payment.receiver.id, payment.amount_ore)
        assert cash.settlement_plan(game) == []


def test_reopening_clears_adjustments_and_recompletion_does_not_double_apply(app):
    with app.app_context():
        game = cash.create_game("Diff igen", date.today(), players(), 20_000)
        db.session.commit()
        cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, [35_100, 25_000, 15_000, 5_000])})
        cash.complete_game(game)
        first = [entry.net for entry in game.entries]
        cash.reopen_game(game)
        assert all(entry.cash_out_adjustment_ore == 0 for entry in game.entries)
        cash.complete_game(game)
        assert [entry.net for entry in game.entries] == first


def test_concurrent_cashgame_changes_roll_back_the_entire_second_transaction(app):
    with app.app_context():
        people = players()
        game = cash.create_game("Två flikar", date.today(), people, 20_000)
        db.session.commit()
        with Session(db.engine) as other:
            old_game = other.get(CashGame, game.id)
            cash.add_buy_in(game, people[0], 5_000)
            db.session.commit()
            old_game.entries[0].buy_ins.append(CashGameBuyIn(amount_ore=7_000))
            old_game.version += 1
            with pytest.raises(StaleDataError):
                other.commit()
            other.rollback()
        db.session.expire_all()
        assert game.total_buy_ins == 85_000


def test_routes_show_diff_preview_and_allow_closing_with_difference(app, client):
    with app.app_context():
        game = cash.create_game("Diff i webben", date.today(), players(), 20_000)
        db.session.commit()
        cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, [35_001, 25_000, 15_000, 5_000])})
        db.session.commit()
        game_id, version = game.id, game.version
    csrf = token(client)
    page = client.get(f"/cashgame/{game_id}")
    assert "Diff vid bordet: +0,01 kr" in page.text
    response = client.post(f"/cashgame/{game_id}/complete", data={"csrf_token": csrf, "version": version}, follow_redirects=True)
    assert response.status_code == 200
    assert "Swish-förslag är klara" in response.text
    assert "Diff −0,01 kr" in response.text


def test_non_ascii_csrf_is_rejected_without_server_error(client):
    token(client)
    assert client.post("/cashgame/new", data={"csrf_token": "felaktigtåäö"}).status_code == 400


def test_winner_is_highest_net_after_all_buy_ins_not_largest_cash_out(app, client):
    with app.app_context():
        people = players()
        game = cash.create_game("Rätt vinnare", date.today(), people, 20_000)
        db.session.commit()
        cash.add_buy_in(game, people[0], 20_000)
        cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, [40_000, 35_000, 15_000, 10_000])})
        cash.complete_game(game)
        db.session.commit()
        game_id = game.id
        winners = cash.cashgame_winners(game)
        assert len(winners) == 1
        assert winners[0]["entry"].player.name == "Elvis"
        assert winners[0]["image"] == "elvis.png"
    page = client.get(f"/cashgame/{game_id}")
    assert page.status_code == 200
    assert 'class="cash-champion-image"' in page.text
    assert 'href="/elvis"' in page.text
    assert "Kungen tog betalt för audiensen." in page.text


def test_tied_winners_use_adjusted_profit_and_survive_completed_swish(app):
    with app.app_context():
        game = cash.create_game("Delad tron", date.today(), players(), 20_000)
        db.session.commit()
        cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, [35_001, 35_000, 5_000, 5_000])})
        cash.complete_game(game)
        assert {winner["slug"] for winner in cash.cashgame_winners(game)} == {"leo", "elvis"}
        for payment in cash.settlement_plan(game):
            cash.record_transfer(game, payment.payer.id, payment.receiver.id, payment.amount_ore)
        assert cash.settlement_plan(game) == []
        assert {winner["entry"].net for winner in cash.cashgame_winners(game)} == {15_000}


def test_winner_portrait_uses_the_explicit_profile_binding_for_renamed_players(app):
    with app.app_context():
        people = players()
        people[0].name = "Kassakungen"
        people[0].name_key = "kassakungen"
        db.session.add(AppMeta(key="cashgame.profile.erik", value=str(people[0].id)))
        game = game_with_result(people)
        winner = cash.cashgame_winners(game)[0]
        assert winner["slug"] == "erik"
        assert winner["image"] == "erik.png"
        assert cash.profile_context("erik")["cashgame_player"].id == people[0].id


def test_unknown_winner_has_no_portrait_and_does_not_promote_a_known_runner_up(app):
    with app.app_context():
        people = players()
        people[0].name = "Gästspelaren"
        people[0].name_key = "gästspelaren"
        game = game_with_result(people)
        winners = cash.cashgame_winners(game)
        assert len(winners) == 1
        assert winners[0]["entry"].player.name == "Gästspelaren"
        assert winners[0]["slug"] is None
        assert winners[0]["image"] is None


def test_open_game_and_break_even_game_have_no_winner_banner(app, client):
    with app.app_context():
        game = cash.create_game("Inte färdig", date.today(), players(), 20_000)
        db.session.commit()
        cash.save_cash_outs(game, {entry.id: amount for entry, amount in zip(game.entries, [35_000, 25_000, 15_000, 5_000])})
        assert cash.cashgame_winners(game) == []
        cash.save_cash_outs(game, {entry.id: 20_000 for entry in game.entries})
        cash.complete_game(game)
        db.session.commit()
        assert cash.cashgame_winners(game) == []
        game_id = game.id
    assert 'data-cash-champion' not in client.get(f"/cashgame/{game_id}").text
