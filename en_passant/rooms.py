"""In-memory online game rooms shared by every connected client.

A room holds the authoritative board. Seats are filled by client tokens (humans)
or by the literal string "bot". All mutation happens under a single lock.
"""

import random
import string
import threading
import time
from dataclasses import dataclass, field

import chess

BOT = "bot"
QUICK_MATCH_WAIT = 6.0  # seconds before a quick match falls back to a bot
_LOCK = threading.RLock()
_ROOMS: dict[str, "Room"] = {}


@dataclass
class Room:
    code: str
    white: str = ""
    black: str = ""
    bot_level: int = 2
    quick: bool = False
    created: float = field(default_factory=time.monotonic)
    board: chess.Board = field(default_factory=chess.Board)
    san_list: list[str] = field(default_factory=list)
    last_move: list[int] = field(default_factory=list)
    resigned: str = ""  # "white" | "black"
    bot_thinking: bool = False
    version: int = 0

    def color_of(self, player: str) -> str:
        if player and player == self.white:
            return "white"
        if player and player == self.black:
            return "black"
        return ""

    @property
    def full(self) -> bool:
        return bool(self.white and self.black)

    @property
    def over(self) -> bool:
        return bool(self.resigned) or self.board.is_game_over(claim_draw=True)

    @property
    def status(self) -> str:
        if self.resigned:
            return f"{self.resigned.capitalize()} resigned"
        if not self.full:
            return "Waiting for an opponent…"
        outcome = self.board.outcome(claim_draw=True)
        if outcome:
            term = outcome.termination.name.replace("_", " ").capitalize()
            if outcome.winner is None:
                return f"Draw · {term}"
            return f"{'White' if outcome.winner else 'Black'} wins · {term}"
        who = "White" if self.board.turn else "Black"
        return f"{who} to move" + (" · Check!" if self.board.is_check() else "")

    def opponent_label(self, color: str) -> str:
        seat = self.black if color == "white" else self.white
        if not seat:
            return "Waiting…"
        return f"Bot · level {self.bot_level}" if seat == BOT else "Opponent"


def _new_code() -> str:
    while True:
        code = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        if code not in _ROOMS:
            return code


def get(code: str) -> Room | None:
    with _LOCK:
        return _ROOMS.get(code)


def create(player: str, color: str = "random", bot_level: int | None = None, quick: bool = False) -> Room:
    """Open a room. With `bot_level` the other seat is filled by the bot straight away."""
    with _LOCK:
        if color == "random":
            color = random.choice(["white", "black"])
        room = Room(code=_new_code(), quick=quick, bot_level=bot_level or 2)
        setattr(room, color, player)
        if bot_level:
            setattr(room, "black" if color == "white" else "white", BOT)
        _ROOMS[room.code] = room
        _prune()
        return room


def quick_match(player: str) -> Room:
    """Join someone who is waiting for a quick match, or open a room and wait."""
    with _LOCK:
        for room in _ROOMS.values():
            if room.quick and not room.full and not room.color_of(player):
                join(room, player)
                return room
        return create(player, quick=True)


def join(room: Room, player: str) -> str:
    """Seat `player` and return their colour ("" for a spectator)."""
    with _LOCK:
        seat = room.color_of(player)
        if seat:
            return seat
        for color in ("white", "black"):
            if not getattr(room, color):
                setattr(room, color, player)
                room.version += 1
                return color
        return ""


def tick(room: Room):
    """Housekeeping: a quick match nobody joined becomes a game against the bot."""
    with _LOCK:
        if room.quick and not room.full and time.monotonic() - room.created > QUICK_MATCH_WAIT:
            for color in ("white", "black"):
                if not getattr(room, color):
                    setattr(room, color, BOT)
            room.version += 1


def play(room: Room, player: str, move: chess.Move) -> bool:
    """Apply a human move if it is legal and it is that player's turn."""
    with _LOCK:
        color = room.color_of(player)
        if not color or room.over or not room.full:
            return False
        if room.board.turn != (color == "white") or move not in room.board.legal_moves:
            return False
        _apply(room, move)
        return True


def _apply(room: Room, move: chess.Move):
    room.san_list.append(room.board.san(move))
    room.board.push(move)
    room.last_move = [move.from_square, move.to_square]
    room.version += 1


def resign(room: Room, player: str):
    with _LOCK:
        color = room.color_of(player)
        if color and not room.over and room.full:
            room.resigned = color
            room.version += 1


def claim_bot_turn(room: Room) -> chess.Board | None:
    """If it is the bot's move and nobody is computing it yet, claim the job."""
    with _LOCK:
        if room.over or not room.full or room.bot_thinking:
            return None
        seat = room.white if room.board.turn else room.black
        if seat != BOT:
            return None
        room.bot_thinking = True
        room.version += 1
        return room.board.copy()


def finish_bot_turn(room: Room, move: chess.Move | None, expected_fen: str):
    with _LOCK:
        room.bot_thinking = False
        if move and not room.over and room.board.fen() == expected_fen:
            _apply(room, move)
        else:
            room.version += 1


def _prune(max_age: float = 6 * 3600):
    now = time.monotonic()
    for code in [c for c, r in _ROOMS.items() if now - r.created > max_age]:
        del _ROOMS[code]
