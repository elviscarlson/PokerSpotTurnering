from __future__ import annotations

from datetime import date, datetime, timezone

from .extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AppMeta(db.Model):
    __tablename__ = "app_meta"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    key = db.Column(
        db.String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    value = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    name = db.Column(
        db.String(80),
        nullable=False,
    )

    name_key = db.Column(
        db.String(80),
        nullable=False,
        unique=True,
        index=True,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    tournament_entries = db.relationship(
        "TournamentPlayer",
        back_populates="player",
        lazy="selectin",
    )


class Tournament(db.Model):
    __tablename__ = "tournaments"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    name = db.Column(
        db.String(120),
        nullable=False,
    )

    tournament_date = db.Column(
        db.Date,
        nullable=False,
        default=date.today,
    )

    target_duration_minutes = db.Column(
        db.Integer,
        nullable=False,
    )

    buy_in = db.Column(
        db.Integer,
        nullable=False,
    )

    bounty_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    bounty_amount = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="DRAFT",
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    players = db.relationship(
        "TournamentPlayer",
        back_populates="tournament",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TournamentPlayer.id",
    )

    prizes = db.relationship(
        "Prize",
        back_populates="tournament",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Prize.place",
    )

    structure = db.relationship(
        "TournamentStructure",
        back_populates="tournament",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    runtime = db.relationship(
        "TournamentRuntime",
        back_populates="tournament",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    result = db.relationship(
        "TournamentResult",
        back_populates="tournament",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    bounties = db.relationship(
        "Bounty",
        back_populates="tournament",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    events = db.relationship(
        "TournamentEvent",
        back_populates="tournament",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TournamentEvent.created_at",
    )

    @property
    def player_count(self) -> int:
        return len(self.players)

    @property
    def active_player_count(self) -> int:
        return sum(
            1
            for entry in self.players
            if entry.status == "ACTIVE"
        )

    @property
    def total_entries(self) -> int:
        return sum(
            entry.buy_in_count
            for entry in self.players
        )


    @property
    def total_buyins(self) -> int:
        return (
            self.total_entries
            * self.buy_in
        )


    @property
    def bounty_pool(self) -> int:
        if not self.bounty_enabled:
            return 0

        return (
            self.total_entries
            * self.bounty_amount
        )


    @property
    def regular_prize_pool(self) -> int:
        return (
            self.total_buyins
            - self.bounty_pool
        )

    @property
    def total_prizes(self) -> int:
        return sum(
            prize.amount
            for prize in self.prizes
        )

    @property
    def total_bounty_winnings(self) -> int:
        return sum(
            entry.bounty_winnings
            for entry in self.players
        )

    @property
    def winner(self) -> TournamentPlayer | None:
        return next(
            (
                entry
                for entry in self.players
                if entry.placement == 1
            ),
            None,
        )


class TournamentPlayer(db.Model):
    __tablename__ = "tournament_players"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    player_id = db.Column(
        db.Integer,
        db.ForeignKey("players.id"),
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="ACTIVE",
    )

    buy_in_count = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    elimination_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    placement = db.Column(
        db.Integer,
        nullable=True,
    )

    prize_winnings = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    bounty_winnings = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    tournament = db.relationship(
        "Tournament",
        back_populates="players",
    )

    player = db.relationship(
        "Player",
        back_populates="tournament_entries",
    )

    bounties_won = db.relationship(
        "Bounty",
        foreign_keys="Bounty.winner_entry_id",
        back_populates="winner_entry",
        lazy="selectin",
    )

    elimination_bounties = db.relationship(
        "Bounty",
        foreign_keys="Bounty.eliminated_entry_id",
        back_populates="eliminated_entry",
        lazy="selectin",
        order_by="Bounty.elimination_number",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "tournament_id",
            "player_id",
            name="uq_tournament_player",
        ),
    )

    @property
    def total_winnings(self) -> int:
        return (
            self.prize_winnings
            + self.bounty_winnings
        )


class Prize(db.Model):
    __tablename__ = "prizes"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    place = db.Column(
        db.Integer,
        nullable=False,
    )

    amount = db.Column(
        db.Integer,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    tournament = db.relationship(
        "Tournament",
        back_populates="prizes",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "tournament_id",
            "place",
            name="uq_tournament_prize_place",
        ),
    )


class TournamentStructure(db.Model):
    __tablename__ = "tournament_structures"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    starting_stack = db.Column(
        db.Integer,
        nullable=False,
    )

    chip_breakdown = db.Column(
        db.JSON,
        nullable=False,
    )

    level_duration_minutes = db.Column(
        db.Integer,
        nullable=False,
    )

    estimated_duration_min_minutes = db.Column(
        db.Integer,
        nullable=False,
    )

    estimated_duration_max_minutes = db.Column(
        db.Integer,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    tournament = db.relationship(
        "Tournament",
        back_populates="structure",
    )

    blind_levels = db.relationship(
        "BlindLevel",
        back_populates="structure",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="BlindLevel.position",
    )

    @property
    def total_chips(self) -> int:
        return (
            self.starting_stack
            * self.tournament.total_entries
        )


class BlindLevel(db.Model):
    __tablename__ = "blind_levels"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    structure_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournament_structures.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    position = db.Column(
        db.Integer,
        nullable=False,
    )

    small_blind = db.Column(
        db.Integer,
        nullable=False,
    )

    big_blind = db.Column(
        db.Integer,
        nullable=False,
    )

    duration_seconds = db.Column(
        db.Integer,
        nullable=False,
    )

    structure = db.relationship(
        "TournamentStructure",
        back_populates="blind_levels",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "structure_id",
            "position",
            name="uq_blind_level_position",
        ),
    )

    @property
    def duration_minutes(self) -> int:
        return (
            self.duration_seconds
            // 60
        )


class TournamentRuntime(db.Model):
    __tablename__ = "tournament_runtimes"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    current_level_position = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    timer_started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    remaining_seconds_when_paused = db.Column(
        db.Integer,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    tournament = db.relationship(
        "Tournament",
        back_populates="runtime",
    )


class TournamentResult(db.Model):
    __tablename__ = "tournament_results"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    winner_entry_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournament_players.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    completed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    duration_seconds = db.Column(
        db.Integer,
        nullable=True,
    )

    winner_retained_bounty = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    status_before_completion = db.Column(
        db.String(20),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    tournament = db.relationship(
        "Tournament",
        back_populates="result",
    )

    winner_entry = db.relationship(
        "TournamentPlayer",
        foreign_keys=[winner_entry_id],
    )


class Bounty(db.Model):
    __tablename__ = "bounties"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    winner_entry_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournament_players.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    eliminated_entry_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournament_players.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    elimination_number = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    amount = db.Column(
        db.Integer,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    tournament = db.relationship(
        "Tournament",
        back_populates="bounties",
    )

    winner_entry = db.relationship(
        "TournamentPlayer",
        foreign_keys=[winner_entry_id],
        back_populates="bounties_won",
    )

    eliminated_entry = db.relationship(
        "TournamentPlayer",
        foreign_keys=[eliminated_entry_id],
        back_populates="elimination_bounties",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "eliminated_entry_id",
            "elimination_number",
            name="uq_bounty_elimination",
        ),
    )


class TournamentEvent(db.Model):
    __tablename__ = "tournament_events"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "tournaments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    event_type = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    message = db.Column(
        db.String(255),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    tournament = db.relationship(
        "Tournament",
        back_populates="events",
    )


class CashGame(db.Model):
    __tablename__ = "cash_games"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    played_on = db.Column(db.Date, nullable=False, default=date.today, index=True)
    status = db.Column(db.String(20), nullable=False, default="OPEN")
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    entries = db.relationship("CashGameEntry", back_populates="game", cascade="all, delete-orphan", lazy="selectin", order_by="CashGameEntry.id")
    transfers = db.relationship("CashGameTransfer", back_populates="game", cascade="all, delete-orphan", lazy="selectin", order_by="CashGameTransfer.id")
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (db.CheckConstraint("status IN ('OPEN', 'COMPLETED')", name="ck_cash_game_status"),)

    @property
    def total_buy_ins(self):
        return sum(entry.total_buy_ins for entry in self.entries)

    @property
    def total_cash_outs(self):
        return sum(entry.cash_out_ore or 0 for entry in self.entries)


class CashGameEntry(db.Model):
    __tablename__ = "cash_game_entries"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("cash_games.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False, index=True)
    cash_out_ore = db.Column(db.Integer, nullable=True)
    cash_out_adjustment_ore = db.Column(db.Integer, nullable=False, default=0)
    game = db.relationship("CashGame", back_populates="entries")
    player = db.relationship("Player", lazy="selectin")
    buy_ins = db.relationship("CashGameBuyIn", back_populates="entry", cascade="all, delete-orphan", lazy="selectin", order_by="CashGameBuyIn.id")
    __table_args__ = (
        db.UniqueConstraint("game_id", "player_id", name="uq_cash_game_player"),
        db.CheckConstraint("cash_out_ore IS NULL OR cash_out_ore >= 0", name="ck_cash_out_nonnegative"),
    )

    @property
    def total_buy_ins(self):
        return sum(buy_in.amount_ore for buy_in in self.buy_ins if buy_in.voided_at is None)

    @property
    def buy_in_count(self):
        return sum(buy_in.voided_at is None for buy_in in self.buy_ins)

    @property
    def net(self):
        return None if self.cash_out_ore is None else self.adjusted_cash_out_ore - self.total_buy_ins

    @property
    def adjusted_cash_out_ore(self):
        return None if self.cash_out_ore is None else self.cash_out_ore + (self.cash_out_adjustment_ore or 0)


class CashGameBuyIn(db.Model):
    __tablename__ = "cash_game_buy_ins"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("cash_game_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_ore = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    entry = db.relationship("CashGameEntry", back_populates="buy_ins")
    __table_args__ = (db.CheckConstraint("amount_ore > 0", name="ck_cash_buy_in_positive"),)


class CashGameTransfer(db.Model):
    __tablename__ = "cash_game_transfers"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("cash_games.id", ondelete="CASCADE"), nullable=False, index=True)
    payer_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    amount_ore = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    game = db.relationship("CashGame", back_populates="transfers")
    payer = db.relationship("Player", foreign_keys=[payer_id], lazy="selectin")
    receiver = db.relationship("Player", foreign_keys=[receiver_id], lazy="selectin")
    __table_args__ = (
        db.CheckConstraint("amount_ore > 0", name="ck_cash_transfer_positive"),
        db.CheckConstraint("payer_id != receiver_id", name="ck_cash_transfer_different_players"),
    )



