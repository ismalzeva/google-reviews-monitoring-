"""App configuration — secrets from .env, never hardcoded."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///data/grm.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('SESSION_LIFETIME_HOURS', 24)) * 3600

    # App
    APP_NAME = os.environ.get('APP_NAME', 'Google Reviews Monitoring')
    APP_PORT = int(os.environ.get('APP_PORT', 8083))


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
