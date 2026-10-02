"""A small chess engine: iterative-deepening negamax with alpha-beta pruning,
quiescence search, MVV-LVA move ordering and a light positional evaluation."""

import math
import random
import time

import chess

MATE = 100_000

PIECE_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# level -> (max depth, time budget in seconds, root noise in centipawns)
LEVELS = {
    1: (1, 0.2, 90),
    2: (2, 0.6, 25),
    3: (3, 1.5, 0),
    4: (6, 3.0, 0),
}


class _Timeout(Exception):
    pass


def _centrality(square: int) -> int:
    f, r = chess.square_file(square), chess.square_rank(square)
    return 6 - int(abs(f - 3.5) + abs(r - 3.5))  # 0 (corner) .. 6 (centre)


def _piece_bonus(piece: chess.Piece, square: int) -> int:
    t = piece.piece_type
    rank = chess.square_rank(square)
    if not piece.color:
        rank = 7 - rank
    if t == chess.PAWN:
        return rank * 8 + (_centrality(square) * 2 if rank < 5 else 0)
    if t in (chess.KNIGHT, chess.BISHOP):
        return _centrality(square) * 5
    if t == chess.ROOK:
        return 12 if rank == 6 else 0
    if t == chess.QUEEN:
        return _centrality(square)
    # King: hide it away from the centre while there is material on the board
    return -_centrality(square) * 4


def evaluate(board: chess.Board) -> int:
    """Static evaluation in centipawns from White's point of view."""
    score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUE[piece.piece_type] + _piece_bonus(piece, square)
        score += value if piece.color else -value
    return score


def _order_key(board: chess.Board):
    def key(move: chess.Move) -> int:
        s = 0
        if board.is_capture(move):
            victim = board.piece_type_at(move.to_square) or chess.PAWN  # en passant
            attacker = board.piece_type_at(move.from_square) or chess.PAWN
            s += 10 * PIECE_VALUE[victim] - PIECE_VALUE[attacker] + 10_000
        if move.promotion:
            s += PIECE_VALUE[move.promotion] + 9_000
        if board.gives_check(move):
            s += 50
        return s

    return key


class _Search:
    def __init__(self, deadline: float):
        self.deadline = deadline
        self.nodes = 0

    def _tick(self):
        self.nodes += 1
        if self.nodes & 1023 == 0 and time.monotonic() > self.deadline:
            raise _Timeout

    def quiesce(self, board: chess.Board, alpha: int, beta: int, depth: int = 0) -> int:
        self._tick()
        stand = evaluate(board) * (1 if board.turn else -1)
        if stand >= beta:
            return beta
        alpha = max(alpha, stand)
        if depth >= 4:
            return alpha
        captures = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
        captures.sort(key=_order_key(board), reverse=True)
        for move in captures:
            board.push(move)
            score = -self.quiesce(board, -beta, -alpha, depth + 1)
            board.pop()
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        return alpha

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self._tick()
        if board.is_checkmate():
            return -MATE + ply
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        if depth <= 0:
            return self.quiesce(board, alpha, beta)
        moves = sorted(board.legal_moves, key=_order_key(board), reverse=True)
        for move in moves:
            board.push(move)
            score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        return alpha


def best_move(board: chess.Board, level: int = 2) -> chess.Move | None:
    """Pick a move for the side to move at the given strength level (1-4)."""
    max_depth, budget, noise = LEVELS.get(level, LEVELS[2])
    board = board.copy()
    moves = list(board.legal_moves)
    if not moves:
        return None
    if len(moves) == 1:
        return moves[0]

    search = _Search(time.monotonic() + budget)
    moves.sort(key=_order_key(board), reverse=True)
    best, scores = moves[0], {m: 0 for m in moves}

    for depth in range(1, max_depth + 1):
        try:
            current: dict[chess.Move, int] = {}
            alpha = -MATE - 1
            for move in moves:
                board.push(move)
                score = -search.negamax(board, depth - 1, -MATE - 1, -alpha, 1)
                board.pop()
                current[move] = score
                alpha = max(alpha, score)
        except _Timeout:
            break
        scores = current
        moves.sort(key=lambda m: scores[m], reverse=True)  # best first next round
        best = moves[0]
        if abs(scores[best]) > MATE - 100:  # forced mate found
            break

    if noise:
        return max(scores, key=lambda m: scores[m] + random.uniform(-noise, noise))
    return best


def white_percentage(board: chess.Board) -> float:
    """Evaluation squashed into 0-100 for the eval bar (50 = equal)."""
    if board.is_checkmate():
        return 0.0 if board.turn else 100.0
    material = sum(
        PIECE_VALUE[p.piece_type] * (1 if p.color else -1) for p in board.piece_map().values()
    )
    return round(50 + 50 * math.tanh(material / 700), 1)


def material_advantage(board: chess.Board) -> int:
    """Material difference in pawns, positive when White is ahead."""
    return round(
        sum(PIECE_VALUE[p.piece_type] * (1 if p.color else -1) for p in board.piece_map().values())
        / 100
    )
