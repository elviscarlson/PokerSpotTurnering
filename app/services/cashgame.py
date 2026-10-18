from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re

from sqlalchemy import select

from app.extensions import db
from app.models import AppMeta, CashGame, CashGameBuyIn, CashGameEntry, CashGameTransfer, Player, utc_now

PROFILE_SLUGS = ("leo", "elvis", "hugo", "olle", "elias", "erik")


class CashGameError(ValueError):
    pass


def validate_amount(amount: int, *, allow_zero=False):
    if type(amount) is not int or amount < (0 if allow_zero else 1) or amount > 100_000_000:
        raise CashGameError("Beloppet är ogiltigt. Ange kronor med högst två decimaler.")


def parse_money(value: str, *, allow_zero=False) -> int:
    text = str(value).strip().replace(" ", "").replace("\u00a0", "")
    if not re.fullmatch(r"\d{1,7}(?:[.,]\d{1,2})?", text):
        raise CashGameError("Ange ett belopp i kronor med högst två decimaler.")
    ore = int(Decimal(text.replace(",", ".")) * 100)
    if ore > 100_000_000 or ore < (0 if allow_zero else 1):
        raise CashGameError("Beloppet måste vara mellan 0,01 och 1 000 000 kr." if not allow_zero else "Beloppet måste vara mellan 0 och 1 000 000 kr.")
    return ore


def money(ore: int, signed=False) -> str:
    sign = "−" if ore < 0 else "+" if signed and ore > 0 else ""
    kronor, decimals = divmod(abs(ore), 100)
    value = f"{kronor:,}".replace(",", " ")
    return f"{sign}{value}" + (f",{decimals:02d}" if decimals else "") + " kr"


def money_input(ore: int | None) -> str:
    if ore is None:
        return ""
    return f"{ore // 100}.{ore % 100:02d}"


def require_open(game: CashGame):
    if game.status != "OPEN":
        raise CashGameError("Spelkvällen är avslutad. Öppna den igen innan du ändrar inköp eller utcheckning.")


def touch(game: CashGame):
    # Every money mutation updates the parent version. SQLAlchemy rejects concurrent writes.
    game.version += 1


def create_game(name: str, played_on: date, players: list[Player], initial_buy_in: int) -> CashGame:
    validate_amount(initial_buy_in)
    name = " ".join(name.split())
    if not name or len(name) > 120:
        raise CashGameError("Spelkvällen behöver ett namn på högst 120 tecken.")
    if len({player.id for player in players}) != len(players) or len(players) < 2:
        raise CashGameError("Välj minst två olika spelare.")
    game = CashGame(name=name, played_on=played_on, status="OPEN")
    for player in players:
        game.entries.append(CashGameEntry(player=player, buy_ins=[CashGameBuyIn(amount_ore=initial_buy_in)]))
    db.session.add(game)
    return game


def add_buy_in(game: CashGame, player: Player, amount: int):
    require_open(game)
    validate_amount(amount)
    entry = next((entry for entry in game.entries if entry.player_id == player.id), None)
    if entry is None:
        if not player.is_active:
            raise CashGameError("Återställ spelaren innan du lägger till den i en ny spelkväll.")
        entry = CashGameEntry(player=player)
        game.entries.append(entry)
    entry.buy_ins.append(CashGameBuyIn(amount_ore=amount))
    # A new buy-in makes an earlier checkout incomplete until it is confirmed again.
    entry.cash_out_ore = None
    touch(game)


def undo_buy_in(game: CashGame, buy_in_id: int):
    require_open(game)
    buy_in = next((b for entry in game.entries for b in entry.buy_ins if b.id == buy_in_id), None)
    if buy_in is None or buy_in.voided_at is not None:
        raise CashGameError("Inköpet finns inte eller är redan ångrat.")
    buy_in.voided_at = utc_now()
    buy_in.entry.cash_out_ore = None
    touch(game)


def save_cash_outs(game: CashGame, amounts: dict[int, int | None]):
    require_open(game)
    if set(amounts) != {entry.id for entry in game.entries}:
        raise CashGameError("Spelarlistan har ändrats. Ladda om sidan och försök igen.")
    for amount in amounts.values():
        if amount is not None:
            validate_amount(amount, allow_zero=True)
    for entry in game.entries:
        entry.cash_out_ore = amounts[entry.id]
    touch(game)


def difference_adjustments(game: CashGame) -> dict[int, int]:
    if any(entry.cash_out_ore is None for entry in game.entries):
        raise CashGameError("Ange utcheckning för alla spelare. Skriv 0 om en spelare förlorat allt.")
    difference = game.total_buy_ins - game.total_cash_outs
    if not difference:
        return {}
    winners = sorted((entry for entry in game.entries if entry.cash_out_ore > entry.total_buy_ins), key=lambda entry: entry.player_id)
    if not winners:
        raise CashGameError("Skillnaden kan inte fördelas eftersom ingen spelare ligger plus. Kontrollera utcheckningarna.")
    adjustments = {entry.id: 0 for entry in winners}
    if difference > 0:
        share, remainder = divmod(difference, len(winners))
        return {entry.id: share + int(index < remainder) for index, entry in enumerate(winners)}
    # Split an excess equally, capping each deduction at that winner's profit.
    # Redistribute the rest so the adjustment never turns a winner into a loser.
    remaining = -difference
    capacities = {entry.id: entry.cash_out_ore - entry.total_buy_ins for entry in winners}
    while remaining:
        eligible = [entry.id for entry in winners if capacities[entry.id] > 0]
        if not eligible:
            raise CashGameError("Skillnaden överstiger vinnarnas vinster. Kontrollera utcheckningarna.")
        share, remainder = divmod(remaining, len(eligible))
        for index, entry_id in enumerate(eligible):
            deduction = min(capacities[entry_id], share + int(index < remainder))
            capacities[entry_id] -= deduction
            adjustments[entry_id] -= deduction
            remaining -= deduction
    return adjustments


def complete_game(game: CashGame):
    require_open(game)
    adjustments = difference_adjustments(game)
    if not game.total_buy_ins:
        raise CashGameError("Lägg till minst ett inköp innan spelkvällen avslutas.")
    for entry in game.entries:
        entry.cash_out_adjustment_ore = adjustments.get(entry.id, 0)
    game.status = "COMPLETED"
    touch(game)


def reopen_game(game: CashGame):
    if game.status != "COMPLETED":
        raise CashGameError("Spelkvällen är redan öppen.")
    if any(payment.voided_at is None for payment in game.transfers):
        raise CashGameError("Ångra registrerade Swish-betalningar innan du ändrar spelkvällens resultat.")
    game.status = "OPEN"
    for entry in game.entries:
        entry.cash_out_adjustment_ore = 0
    touch(game)


@dataclass
class SuggestedTransfer:
    payer: Player
    receiver: Player
    amount_ore: int


def remaining_balances(game: CashGame) -> dict[int, int]:
    if game.status != "COMPLETED" or any(entry.net is None for entry in game.entries):
        raise CashGameError("Avsluta spelkvällen innan Swish-förslaget räknas ut.")
    balances = {entry.player_id: entry.net for entry in game.entries}
    if sum(balances.values()) != 0:
        raise CashGameError("Spelkvällens inköp och utcheckningar är inte i balans.")
    for payment in game.transfers:
        if payment.voided_at is None:
            balances[payment.payer_id] += payment.amount_ore
            balances[payment.receiver_id] -= payment.amount_ore
    return balances


def settlement_plan(game: CashGame) -> list[SuggestedTransfer]:
    balances = remaining_balances(game)
    players = {entry.player_id: entry.player for entry in game.entries}
    debtors = sorted([[key, -value] for key, value in balances.items() if value < 0], key=lambda row: (-row[1], row[0]))
    creditors = sorted([[key, value] for key, value in balances.items() if value > 0], key=lambda row: (-row[1], row[0]))
    plan = []
    payer = receiver = 0
    while payer < len(debtors) and receiver < len(creditors):
        amount = min(debtors[payer][1], creditors[receiver][1])
        plan.append(SuggestedTransfer(players[debtors[payer][0]], players[creditors[receiver][0]], amount))
        debtors[payer][1] -= amount
        creditors[receiver][1] -= amount
        if not debtors[payer][1]:
            payer += 1
        if not creditors[receiver][1]:
            receiver += 1
    return plan


def record_transfer(game: CashGame, payer_id: int, receiver_id: int, amount: int):
    validate_amount(amount)
    balances = remaining_balances(game)
    if payer_id == receiver_id or payer_id not in balances or receiver_id not in balances:
        raise CashGameError("Välj två olika spelare från den här spelkvällen.")
    if amount <= 0 or amount > min(-balances[payer_id], balances[receiver_id]):
        raise CashGameError("Beloppet är högre än den kvarvarande skulden eller fordran.")
    game.transfers.append(CashGameTransfer(payer_id=payer_id, receiver_id=receiver_id, amount_ore=amount))
    touch(game)


def undo_transfer(game: CashGame, transfer_id: int):
    payment = next((payment for payment in game.transfers if payment.id == transfer_id), None)
    if payment is None or payment.voided_at is not None:
        raise CashGameError("Betalningen finns inte eller är redan ångrad.")
    payment.voided_at = utc_now()
    touch(game)


def all_games() -> list[CashGame]:
    return list(db.session.scalars(select(CashGame).order_by(CashGame.played_on.desc(), CashGame.id.desc())))


def summaries(games: list[CashGame], player_id: int | None = None):
    rows = {}
    for game in reversed(games):
        if game.status != "COMPLETED":
            continue
        for entry in game.entries:
            if player_id is not None and entry.player_id != player_id:
                continue
            if not entry.buy_in_count and not entry.cash_out_ore:
                continue
            row = rows.setdefault(entry.player_id, {"player": entry.player, "buy_ins": 0, "cash_outs": 0, "net": 0, "count": 0, "wins": 0, "history": [], "series": [{"label": "Start", "value": 0}]})
            row["buy_ins"] += entry.total_buy_ins
            row["cash_outs"] += entry.adjusted_cash_out_ore
            row["net"] += entry.net
            row["count"] += 1
            row["wins"] += int(entry.net > 0)
            row["history"].append({"game": game, "entry": entry})
            row["series"].append({"label": f"{game.played_on:%d/%m/%Y} · {game.name}", "value": row["net"]})
    return sorted(rows.values(), key=lambda row: (-row["net"], row["player"].name.casefold()))


def player_report(player: Player | None, games: list[CashGame]):
    if player is None:
        return None
    rows = summaries(games, player.id)
    return rows[0] if rows else {"player": player, "buy_ins": 0, "cash_outs": 0, "net": 0, "count": 0, "wins": 0, "history": [], "series": []}


def profile_context(slug: str):
    players = list(db.session.scalars(select(Player).order_by(Player.name)))
    binding = db.session.scalar(select(AppMeta).where(AppMeta.key == f"cashgame.profile.{slug}"))
    player = None
    if binding is not None:
        player = next((p for p in players if str(p.id) == binding.value), None)
    else:
        exact = [p for p in players if p.name_key == slug]
        matching = exact or [p for p in players if p.name.split()[0].casefold() == slug]
        if len(matching) == 1:
            player = matching[0]
    games = all_games() if player else []
    return {"cashgame_slug": slug, "cashgame_players": players, "cashgame_player": player, "cashgame_report": player_report(player, games)}
