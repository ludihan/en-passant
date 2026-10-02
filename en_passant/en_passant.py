"""En Passant — a Lichess-style chess site built entirely in Python with Reflex."""

import chess
import reflex as rx

from .state import GLYPH, LEVEL_NAMES, State

SHOWCASE_FEN = "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P1B2/2PBPN2/PP1N1PPP/R2QK2R w KQ - 0 8"


# ---------------------------------------------------------------- shared bits
def nav() -> rx.Component:
    return rx.el.nav(
        rx.link(
            rx.box("♞", class_name="brand-mark"),
            rx.text("En Passant"),
            href="/",
            class_name="brand",
        ),
        rx.box(
            rx.link("Play", href="/play", class_name="nav-link"),
            rx.link("How it works", href="/#tech", class_name="nav-link"),
            rx.link(
                "Play now",
                href="/play",
                class_name="btn btn-primary",
                style={"padding": "9px 16px", "marginLeft": "8px"},
            ),
            class_name="nav-links",
        ),
        class_name="nav",
    )


def showcase_board() -> rx.Component:
    board = chess.Board(SHOWCASE_FEN)
    cells = []
    for r in range(8):
        for c in range(8):
            sq = (7 - r) * 8 + c
            piece = board.piece_at(sq)
            dark = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 0
            cls = f"sq {'dark' if dark else 'light'}"
            if sq in (chess.F3, chess.D2):
                cls += " last"
            cells.append(
                rx.box(
                    rx.el.span(
                        GLYPH[piece.piece_type] if piece else "",
                        class_name=("pc w" if piece.color else "pc b") if piece else "pc",
                    ),
                    class_name=cls,
                )
            )
    return rx.box(rx.box(*cells, class_name="stage-board"), class_name="stage")


def feature(icon: str, title: str, body: str) -> rx.Component:
    return rx.box(
        rx.box(icon, class_name="ico"),
        rx.el.h3(title),
        rx.el.p(body),
        class_name="card",
    )


# ---------------------------------------------------------------- landing page
def index() -> rx.Component:
    return rx.box(
        nav(),
        rx.box(
            rx.box(
                rx.box(rx.box(class_name="dot"), "Free · No sign-up · Play in one click", class_name="eyebrow"),
                rx.el.h1("Chess, ", rx.el.span("beautifully", class_name="grad-text"), " played."),
                rx.el.p(
                    "Challenge a from-scratch engine across four strength levels, or pass the "
                    "board to a friend. Legal-move hints, live evaluation, full move history — "
                    "all in a clean, distraction-free interface.",
                    class_name="lead",
                ),
                rx.box(
                    rx.link("Start playing  →", href="/play", class_name="btn btn-primary btn-lg"),
                    rx.link("See how it's built", href="#tech", class_name="btn btn-lg"),
                    class_name="cta-row",
                ),
                rx.box(
                    rx.box(rx.el.b("4"), rx.el.span("AI levels"), class_name="stat"),
                    rx.box(rx.el.b("100%"), rx.el.span("Pure Python"), class_name="stat"),
                    rx.box(rx.el.b("0"), rx.el.span("Sign-ups"), class_name="stat"),
                    class_name="stats",
                ),
            ),
            showcase_board(),
            class_name="hero",
        ),
        rx.box(
            rx.el.h2("Everything a good game needs"),
            rx.el.p(
                "The features you'd expect from a modern chess site, without the noise.",
                class_name="sub",
            ),
            rx.box(
                feature("♛", "Play the computer", "Four levels from Beginner to Master, powered by a custom alpha-beta engine."),
                feature("♞", "Pass & play", "Share one screen with a friend and play a full over-the-board game."),
                feature("✓", "Legal-move hints", "Pick a piece and see exactly where it can go, captures and checks highlighted."),
                feature("◐", "Live evaluation", "A real-time evaluation bar and captured-material tracker show who's winning."),
                feature("↺", "Takebacks & PGN", "Undo mistakes, flip the board, and export the game as PGN or FEN."),
                feature("♟", "Full rules", "Castling, en passant, promotion, repetition, fifty-move rule and insufficient material."),
                class_name="cards",
            ),
            class_name="section",
        ),
        rx.box(
            rx.el.h2("Under the hood", id="tech"),
            rx.el.p(
                "A full-stack web app with no JavaScript written by hand. State, rules and the "
                "AI all live on the server and stream to the browser over websockets.",
                class_name="sub",
            ),
            rx.box(
                *[
                    rx.el.span(t, class_name="tag")
                    for t in [
                        "Python 3.13",
                        "Reflex",
                        "python-chess",
                        "negamax + alpha-beta",
                        "quiescence search",
                        "iterative deepening",
                        "MVV-LVA move ordering",
                        "background tasks (asyncio)",
                        "websocket state sync",
                        "CSS container queries",
                    ]
                ],
                class_name="tags",
            ),
            class_name="section",
        ),
        rx.box("Built with Python & Reflex · Open source", class_name="footer"),
    )


# ---------------------------------------------------------------- play page
def square(sq) -> rx.Component:
    return rx.box(
        rx.el.span(sq["glyph"].to(str), class_name=sq["pcls"].to(str)),
        rx.el.span(sq["file"].to(str), class_name="coord coord-file"),
        rx.el.span(sq["rank"].to(str), class_name="coord coord-rank"),
        class_name=sq["cls"].to(str),
        on_click=State.click_square(sq["idx"].to(int)),
    )


def promo_button(letter: str, kind: int) -> rx.Component:
    return rx.el.button(
        GLYPH[kind],
        class_name=rx.cond(State.promo_white, "", "bk"),
        on_click=State.choose_promotion(letter),
    )


def promotion_overlay() -> rx.Component:
    return rx.cond(
        State.promo_from != -1,
        rx.box(
            rx.box(
                promo_button("q", chess.QUEEN),
                promo_button("r", chess.ROOK),
                promo_button("b", chess.BISHOP),
                promo_button("n", chess.KNIGHT),
                class_name="promo",
            ),
            class_name="overlay",
            on_click=State.cancel_promotion,
        ),
    )


def player_bar(name, taken, lead, avatar_alt: bool, show_thinking: bool) -> rx.Component:
    return rx.box(
        rx.box(rx.cond(avatar_alt, "♚", "♞"), class_name="avatar"),
        rx.text(name, class_name="pname"),
        rx.el.span(taken, class_name="taken"),
        rx.el.span(lead, class_name="adv"),
        rx.cond(
            show_thinking,
            rx.box(rx.el.i(), rx.el.i(), rx.el.i(), "Thinking", class_name="think"),
        ),
        class_name="player",
    )


def segment(options: list[tuple[str, str]], current, handler) -> rx.Component:
    return rx.box(
        *[
            rx.el.button(
                label,
                class_name=rx.cond(current == value, "on", ""),
                on_click=handler(value),
            )
            for label, value in options
        ],
        class_name="seg",
    )


def move_row(row) -> rx.Component:
    return rx.box(
        rx.el.span(row[0], class_name="n"),
        rx.el.span(row[1]),
        rx.el.span(row[2]),
        class_name="mrow",
    )


def online_panel() -> rx.Component:
    return rx.box(
        rx.el.h4("Play online"),
        rx.el.button(
            "\u26a1  Quick match",
            class_name="btn btn-primary",
            on_click=State.quick_match,
            style={"width": "100%", "marginBottom": "10px"},
        ),
        rx.box(
            rx.el.button("Invite a friend", class_name="btn", on_click=State.invite_friend),
            rx.el.button("Online vs bot", class_name="btn", on_click=State.online_vs_bot),
            class_name="btn-grid",
        ),
        rx.text(
            "Quick match pairs you with a real player, or a bot if nobody shows up. "
            "Colour and bot level follow the settings above.",
            class_name="empty",
            style={"marginTop": "12px"},
        ),
        class_name="panel",
    )


def room_panel() -> rx.Component:
    return rx.box(
        rx.el.h4("Online game"),
        rx.cond(
            State.my_color != "",
            rx.text(
                "You are playing ",
                rx.el.b(State.my_color),
                " · ",
                rx.el.span(State.room, class_name="mono"),
                class_name="empty",
                style={"marginBottom": "12px"},
            ),
            rx.text("You are spectating this game.", class_name="empty"),
        ),
        rx.cond(
            State.waiting,
            rx.text(
                "Send this link to a friend to start the game:",
                class_name="empty",
                style={"marginBottom": "10px"},
            ),
        ),
        rx.box(
            rx.el.button(
                "Copy invite link",
                class_name="btn",
                on_click=rx.call_script("navigator.clipboard.writeText(window.location.href)"),
            ),
            rx.link("Leave", href="/play", class_name="btn"),
            class_name="btn-grid",
        ),
        class_name="panel",
    )


def side_panel() -> rx.Component:
    return rx.box(
        rx.box(
            rx.el.h4("Game"),
            rx.box(
                rx.cond(State.over, "⚑", rx.cond(State.thinking, "⌛", "●")),
                rx.el.span(State.status),
                class_name=rx.cond(State.over, "statusline over", "statusline"),
            ),
            class_name="panel",
        ),
        rx.cond(
            State.room != "",
            room_panel(),
            rx.fragment(
            rx.box(
                rx.el.h4("New game"),
                segment([("vs Computer", "ai"), ("Pass & play", "local")], State.mode, State.set_mode),
                rx.cond(
                    State.mode == "ai",
                    rx.fragment(
                        segment([("Play White", "white"), ("Play Black", "black")], State.side, State.set_side),
                        rx.box(
                            *[
                                rx.el.button(
                                    name,
                                    class_name=rx.cond(State.level == lvl, "on", ""),
                                    on_click=State.set_level(lvl),
                                )
                                for lvl, name in LEVEL_NAMES.items()
                            ],
                            class_name="seg",
                        ),
                    ),
                ),
                rx.el.button("New game", class_name="btn btn-primary", on_click=State.new_game, style={"width": "100%"}),
                class_name="panel",
            ),
            online_panel(),
            ),
        ),
        rx.box(
            rx.el.h4("Moves"),
            rx.box(
                rx.cond(
                    State.san_list.length() > 0,
                    rx.foreach(State.move_rows, move_row),
                    rx.text("No moves yet — White opens.", class_name="empty"),
                ),
                class_name="moves",
            ),
            class_name="panel",
        ),
        rx.box(
            rx.box(
                rx.el.button("↶  Undo", class_name="btn", on_click=State.undo),
                rx.el.button("⇅  Flip", class_name="btn", on_click=State.flip),
                rx.el.button("Copy PGN", class_name="btn", on_click=State.copy_pgn),
                rx.el.button("Copy FEN", class_name="btn", on_click=State.copy_fen),
                rx.el.button(
                    "Resign",
                    class_name="btn btn-danger",
                    on_click=State.resign,
                    style={"gridColumn": "span 2"},
                ),
                class_name="btn-grid",
            ),
            class_name="panel",
        ),
        class_name="side",
    )


def play() -> rx.Component:
    return rx.box(
        nav(),
        rx.box(
            rx.box(
                player_bar(State.top_name, State.top_taken, State.top_lead, State.flipped, State.thinking & (State.top_name != "You")),
                rx.box(
                    rx.box(
                        rx.box(
                            class_name="evalfill",
                            height=State.eval_pct.to_string() + "%",
                        ),
                        rx.el.span(State.eval_label, class_name="evalnum", style={"bottom": "4px"}),
                        class_name=rx.cond(State.flipped, "evalbar flip", "evalbar"),
                    ),
                    rx.box(
                        rx.box(rx.foreach(State.squares, square), class_name="board"),
                        promotion_overlay(),
                        class_name="board-wrap",
                    ),
                    class_name="board-row",
                ),
                player_bar(State.bottom_name, State.bottom_taken, State.bottom_lead, ~State.flipped, False),
                class_name="board-col",
            ),
            side_panel(),
            class_name="play",
        ),
        rx.cond(State.toast != "", rx.box(State.toast, class_name="toast")),
    )


app = rx.App(
    stylesheets=["/style.css"],
    head_components=[
        rx.el.meta(name="description", content="En Passant — play chess against a custom engine or a friend."),
        rx.el.meta(name="theme-color", content="#0a0b14"),
    ],
)
app.add_page(index, route="/", title="En Passant — Play chess beautifully")
app.add_page(play, route="/play", title="Play · En Passant", on_load=State.new_game)
app.add_page(play, route="/game/[code]", title="Online game · En Passant", on_load=State.enter_room)
