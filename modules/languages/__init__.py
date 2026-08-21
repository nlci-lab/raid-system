import sqlite3

from flask import Blueprint, render_template

from modules.db import LANGUAGES_DB

languages = Blueprint("languages", __name__, template_folder="templates")


def get_conn():
    conn = sqlite3.connect(LANGUAGES_DB)
    conn.row_factory = sqlite3.Row
    return conn


@languages.route("/languages")
def index():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM languages ORDER BY speakers_approx DESC").fetchall()
    families = conn.execute("SELECT * FROM language_families ORDER BY name").fetchall()
    conn.close()
    return render_template("languages_index.html", languages=rows, families=families)
