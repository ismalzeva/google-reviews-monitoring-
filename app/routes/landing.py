"""Public landing / guide / help / about pages (RUN_M3)."""
from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

bp = Blueprint("landing", __name__)

APP_VERSION = "0.9.0"
APP_RELEASE = "Pilot Release"
APP_DEPLOYED_AT = "2026-08-03"


@bp.route("/")
def index():
    """Landing page before login."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return render_template("landing/landing.html", version=APP_VERSION,
                           release=APP_RELEASE)


@bp.route("/guide")
def guide():
    return render_template("landing/guide.html")


@bp.route("/help")
def help_page():
    return render_template("landing/help.html")


@bp.route("/about")
def about():
    return render_template("landing/about.html", version=APP_VERSION,
                           release=APP_RELEASE, deployed_at=APP_DEPLOYED_AT)
