# En Passant

A chess web app written entirely in Python with [Reflex](https://reflex.dev) and [python-chess](https://python-chess.readthedocs.io).

## Features

- **Play the computer** with four difficulty levels, as White or Black.
- **Pass-and-play** on a single device.
- **Online play** with no accounts:
  - *Quick match* pairs you with another waiting player, or with a bot if nobody joins within a few seconds.
  - *Invite a friend* creates a game link you can share.
  - *Online vs bot* starts a private game against the engine.
- Move history, captured pieces and material evaluation bar.
- Undo, resign, flip board, pawn promotion picker.
- Copy the game as PGN or the position as FEN.

## Built-in engine

`en_passant/engine.py` is a small engine with iterative-deepening negamax, alpha-beta pruning, quiescence search, MVV-LVA move ordering and a light positional evaluation. Lower levels search shallower and add random noise to their move choice, so they play weaker.

## Project layout

| Path | Purpose |
| --- | --- |
| `en_passant/en_passant.py` | UI components and routes (`/`, `/play`, `/game/[code]`) |
| `en_passant/state.py` | Reflex state: game flow, board rendering, event handlers |
| `en_passant/engine.py` | Chess engine |
| `en_passant/rooms.py` | Thread-safe in-memory online rooms |
| `assets/` | Static assets and CSS |
| `rxconfig.py` | Reflex configuration |

## Getting started

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run reflex run
```

Then open http://localhost:3000.

## Notes

- Online rooms are stored in memory. Restarting the server ends all online games, and running multiple server processes will not share rooms.

## License

[AGPL-3.0](LICENSE)
