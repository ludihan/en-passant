"""Game state: rules live in python-chess, the engine runs off the event loop."""

import asyncio
from typing import Any

import chess
import reflex as rx

from . import engine, rooms

# Solid glyphs for both colours; CSS paints them white or black.
GLYPH = {
    chess.PAWN: "♟︎",
    chess.KNIGHT: "♞",
    chess.BISHOP: "♝",
    chess.ROOK: "♜",
    chess.QUEEN: "♛",
    chess.KING: "♚",
}
START_COUNTS = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}
LEVEL_NAMES = {1: "Beginner", 2: "Casual", 3: "Club", 4: "Master"}


class State(rx.State):
    # --- settings (applied on "New game") ---
    mode: str = "ai"  # "ai" | "local"
    side: str = "white"  # side the human plays vs the computer
    level: int = 2

    # --- game ---
    fen: str = chess.STARTING_FEN
    san_list: list[str] = []
    selected: int = -1
    targets: list[int] = []
    last_move: list[int] = []
    flipped: bool = False
    thinking: bool = False
    over: bool = False
    status: str = "White to move"
    promo_from: int = -1
    promo_to: int = -1
    gen: int = 0  # bumped whenever the game is reset/rewound; invalidates in-flight AI moves
    toast: str = ""

    # --- online ---
    room: str = ""  # room code; empty when playing locally
    my_color: str = ""  # "white" | "black" | "" (spectator)
    opp_label: str = "Opponent"
    room_version: int = -1
    watch_gen: int = 0

    _board: chess.Board = chess.Board()

    # ---------- settings ----------
    @rx.event
    def set_mode(self, mode: str):
        self.mode = mode

    @rx.event
    def set_side(self, side: str):
        self.side = side

    @rx.event
    def set_level(self, level: int):
        self.level = level

    # ---------- helpers ----------
    @property
    def _human_color(self) -> bool | None:
        if self.room:
            return self.my_color == "white"
        if self.mode != "ai":
            return None
        return self.side != "black"

    @property
    def _player_id(self) -> str:
        return self.router.session.client_token

    def _ai_turn(self) -> bool:
        return (
            not self.room
            and self.mode == "ai"
            and not self.over
            and self._board.turn != self._human_color
        )

    def _sync(self):
        """Refresh derived UI state from the board."""
        board = self._board
        self.fen = board.fen()
        self.selected, self.targets = -1, []
        self.promo_from = self.promo_to = -1
        outcome = board.outcome(claim_draw=True)
        if outcome:
            self.over = True
            term = outcome.termination.name.replace("_", " ").capitalize()
            if outcome.winner is None:
                self.status = f"Draw · {term}"
            else:
                self.status = f"{'White' if outcome.winner else 'Black'} wins · {term}"
        else:
            self.over = False
            who = "White" if board.turn else "Black"
            check = " · Check!" if board.is_check() else ""
            self.status = f"{who} to move{check}"

    def _push(self, move: chess.Move):
        if self.room:
            room = rooms.get(self.room)
            if room and rooms.play(room, self._player_id, move):
                self._load(room)
            return
        self.san_list = [*self.san_list, self._board.san(move)]
        self._board.push(move)
        self.last_move = [move.from_square, move.to_square]
        self._sync()

    # ---------- game flow ----------
    @rx.event
    def new_game(self):
        self.gen += 1
        self.room, self.my_color, self.room_version = "", "", -1
        self._board = chess.Board()
        self.san_list, self.last_move = [], []
        self.thinking = False
        self.over = False
        self.status = "White to move"
        self.flipped = self.mode == "ai" and self.side == "black"
        self._sync()
        if self._ai_turn():
            self.thinking = True
            return State.ai_move

    @rx.event
    def click_square(self, idx: int):
        if self.over or self.thinking or self.promo_from != -1:
            return
        board = self._board
        if self.room and (not self.my_color or board.turn != self._human_color):
            return
        if not self.room and self.mode == "ai" and board.turn != self._human_color:
            return

        if self.selected != -1 and idx in self.targets:
            piece = board.piece_at(self.selected)
            last_rank = chess.square_rank(idx) in (0, 7)
            if piece and piece.piece_type == chess.PAWN and last_rank:
                self.promo_from, self.promo_to = self.selected, idx
                return
            self._push(chess.Move(self.selected, idx))
            if self._ai_turn():
                self.thinking = True
                return State.ai_move
            return

        piece = board.piece_at(idx)
        if piece and piece.color == board.turn and idx != self.selected:
            self.selected = idx
            self.targets = sorted({m.to_square for m in board.legal_moves if m.from_square == idx})
        else:
            self.selected, self.targets = -1, []

    @rx.event
    def choose_promotion(self, piece: str):
        if self.promo_from == -1:
            return
        kind = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}[piece]
        self._push(chess.Move(self.promo_from, self.promo_to, promotion=kind))
        if self._ai_turn():
            self.thinking = True
            return State.ai_move

    @rx.event
    def cancel_promotion(self):
        self.promo_from = self.promo_to = -1
        self.selected, self.targets = -1, []

    @rx.event(background=True)
    async def ai_move(self):
        async with self:
            board, level, gen = self._board.copy(), self.level, self.gen
        move = await asyncio.to_thread(engine.best_move, board, level)
        await asyncio.sleep(0.15)  # let the "thinking" state paint even on instant replies
        async with self:
            if gen != self.gen or move is None:
                return
            self._push(move)
            self.thinking = False

    @rx.event
    def undo(self):
        board = self._board
        if self.room or not board.move_stack or self.thinking:
            return
        self.gen += 1
        board.pop()
        self.san_list = self.san_list[:-1]
        if self.mode == "ai" and board.move_stack and board.turn != self._human_color:
            board.pop()
            self.san_list = self.san_list[:-1]
        self.status = ""
        self.last_move = (
            [board.peek().from_square, board.peek().to_square] if board.move_stack else []
        )
        self._sync()
        if self._ai_turn():  # human is black and we rewound to the very start
            self.thinking = True
            return State.ai_move

    @rx.event
    def resign(self):
        if self.over:
            return
        if self.room:
            room = rooms.get(self.room)
            if room:
                rooms.resign(room, self._player_id)
                self._load(room)
            return
        self.gen += 1
        self.thinking = False
        loser = "White" if self._board.turn else "Black"
        if self.mode == "ai":
            loser = "White" if self._human_color else "Black"
        self.over = True
        self.status = f"{loser} resigned"

    @rx.event
    def flip(self):
        self.flipped = not self.flipped

    @rx.event
    def copy_pgn(self):
        self.toast = "PGN copied"
        return [rx.set_clipboard(self.pgn), State.clear_toast]

    @rx.event
    def copy_fen(self):
        self.toast = "FEN copied"
        return [rx.set_clipboard(self.fen), State.clear_toast]

    @rx.event(background=True)
    async def clear_toast(self):
        await asyncio.sleep(1.8)
        async with self:
            self.toast = ""

    # ---------- online ----------
    def _load(self, room: rooms.Room):
        """Copy the room's authoritative state into this client's state."""
        self._board = room.board.copy()
        self.fen = room.board.fen()
        self.san_list = list(room.san_list)
        self.last_move = list(room.last_move)
        self.status = room.status
        self.over = room.over
        self.thinking = room.bot_thinking
        self.opp_label = room.opponent_label(self.my_color or "white")
        self.room_version = room.version
        self.selected, self.targets = -1, []
        self.promo_from = self.promo_to = -1

    def _open_room(self, room: rooms.Room):
        return rx.redirect(f"/game/{room.code}")

    @rx.event
    def quick_match(self):
        return self._open_room(rooms.quick_match(self._player_id))

    @rx.event
    def invite_friend(self):
        return self._open_room(rooms.create(self._player_id, self.side))

    @rx.event
    def online_vs_bot(self):
        return self._open_room(rooms.create(self._player_id, self.side, bot_level=self.level))

    @rx.event
    def enter_room(self):
        code = self.router.page.params.get("code", "")
        room = rooms.get(code)
        if room is None:
            self.room = ""
            return [rx.toast.error("That game doesn't exist or has expired."), rx.redirect("/play")]
        self.gen += 1
        self.room = code
        self.my_color = rooms.join(room, self._player_id)
        self.flipped = self.my_color == "black"
        self.watch_gen += 1
        self._load(room)
        return State.watch_room(self.watch_gen)

    @rx.event(background=True)
    async def watch_room(self, token: int):
        """Poll the room, mirror changes into this client and run the bot's moves."""
        while True:
            try:
                async with self:
                    if self.watch_gen != token or not self.room:
                        return
                    room = rooms.get(self.room)
                    if room is None:
                        return
                    rooms.tick(room)
                    if room.version != self.room_version:
                        self._load(room)
                    level = room.bot_level
                fen_before = room.board.fen()
                board = rooms.claim_bot_turn(room)
                if board is not None:
                    move = await asyncio.to_thread(engine.best_move, board, level)
                    await asyncio.sleep(0.4)
                    rooms.finish_bot_turn(room, move, fen_before)
            except Exception:  # client went away
                return
            await asyncio.sleep(0.35)

    # ---------- computed ----------
    @rx.var
    def squares(self) -> list[dict[str, Any]]:
        board = chess.Board(self.fen)
        check_sq = board.king(board.turn) if board.is_check() else -1
        out = []
        for r in range(8):
            for c in range(8):
                sq = (7 - r) * 8 + c if not self.flipped else r * 8 + (7 - c)
                f, rk = chess.square_file(sq), chess.square_rank(sq)
                piece = board.piece_at(sq)
                cls = ["sq", "dark" if (f + rk) % 2 == 0 else "light"]
                if sq in self.last_move:
                    cls.append("last")
                if sq == self.selected:
                    cls.append("sel")
                if sq in self.targets:
                    cls.append("cap" if piece or sq == board.ep_square else "tgt")
                if sq == check_sq:
                    cls.append("check")
                if self.promo_to == sq:
                    cls.append("promo-sq")
                out.append(
                    {
                        "idx": sq,
                        "cls": " ".join(cls),
                        "glyph": GLYPH[piece.piece_type] if piece else "",
                        "pcls": ("pc w" if piece.color else "pc b") if piece else "pc",
                        "file": chess.FILE_NAMES[f] if r == 7 else "",
                        "rank": str(rk + 1) if c == 0 else "",
                    }
                )
        return out

    def _captured(self, color: bool) -> str:
        """Glyphs of the pieces of `color` that are missing from the board."""
        board = chess.Board(self.fen)
        out = ""
        for t in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN):
            missing = START_COUNTS[t] - len(board.pieces(t, color))
            out += GLYPH[t] * max(missing, 0)
        return out

    @rx.var
    def taken_by_white(self) -> str:
        return self._captured(chess.BLACK)

    @rx.var
    def taken_by_black(self) -> str:
        return self._captured(chess.WHITE)

    @rx.var
    def material(self) -> int:
        return engine.material_advantage(chess.Board(self.fen))

    @rx.var
    def eval_pct(self) -> float:
        return engine.white_percentage(chess.Board(self.fen))

    @rx.var
    def eval_label(self) -> str:
        m = self.material
        return "0.0" if m == 0 else f"{m:+d}"

    def _name(self, white: bool) -> str:
        if self.room:
            if not self.my_color:
                return "White" if white else "Black"
            return "You" if white == (self.my_color == "white") else self.opp_label
        if self.mode == "ai":
            return "You" if white == (self.side == "white") else f"Bot · {LEVEL_NAMES[self.level]}"
        return "White" if white else "Black"

    @rx.var
    def top_name(self) -> str:
        return self._name(self.flipped)

    @rx.var
    def bottom_name(self) -> str:
        return self._name(not self.flipped)

    @rx.var
    def waiting(self) -> bool:
        return bool(self.room) and self.status.startswith("Waiting")

    @rx.var
    def top_taken(self) -> str:
        return self.taken_by_white if self.flipped else self.taken_by_black

    @rx.var
    def bottom_taken(self) -> str:
        return self.taken_by_black if self.flipped else self.taken_by_white

    @rx.var
    def top_lead(self) -> str:
        lead = self.material if self.flipped else -self.material
        return f"+{lead}" if lead > 0 else ""

    @rx.var
    def bottom_lead(self) -> str:
        lead = -self.material if self.flipped else self.material
        return f"+{lead}" if lead > 0 else ""

    @rx.var
    def move_rows(self) -> list[list[str]]:
        sans = self.san_list
        return [
            [str(i // 2 + 1), sans[i], sans[i + 1] if i + 1 < len(sans) else ""]
            for i in range(0, len(sans), 2)
        ]

    @rx.var
    def pgn(self) -> str:
        return " ".join(
            f"{i // 2 + 1}. {s}" if i % 2 == 0 else s for i, s in enumerate(self.san_list)
        )

    @rx.var
    def promo_white(self) -> bool:
        return chess.Board(self.fen).turn
