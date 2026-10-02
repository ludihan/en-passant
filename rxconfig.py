import reflex as rx

config = rx.Config(
    app_name="en_passant",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(theme=rx.theme(appearance="dark", accent_color="violet")),
    ]
)