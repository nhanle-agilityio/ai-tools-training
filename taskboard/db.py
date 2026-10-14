import sqlite3

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = get_db()
    with current_app.open_resource("schema.sql") as f:
        conn.executescript(f.read().decode("utf8"))


@click.command("init-db")
def init_db_command():
    """Drop and recreate all tables."""
    init_db()
    click.echo("Initialized the database.")


@click.command("seed")
def seed_command():
    """Reset the database and load demo data."""
    from .seed import seed

    init_db()
    seed(get_db())
    click.echo("Seeded demo data.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
