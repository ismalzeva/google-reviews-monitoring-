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

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_REDIRECT_URI = os.environ.get(
        'GOOGLE_REDIRECT_URI',
        'http://localhost:8083/google/callback',
    )

    # Google Business Profile API
    GBP_API_BASE_URL = os.environ.get(
        'GBP_API_BASE_URL',
        'https://businessprofile.googleapis.com/v1',
    )

    # Google Cloud Pub/Sub
    GCP_PROJECT_ID = os.environ.get('GCP_PROJECT_ID', '')
    PUBSUB_TOPIC = os.environ.get('PUBSUB_TOPIC', '')
    PUBSUB_SUBSCRIPTION = os.environ.get('PUBSUB_SUBSCRIPTION', '')
    PUBSUB_SERVICE_ACCOUNT_JSON = os.environ.get('PUBSUB_SERVICE_ACCOUNT_JSON', '')

    # Google OAuth scopes
    GOOGLE_SCOPES = ['https://www.googleapis.com/auth/business.manage']

    # GBP API version info
    GBP_API_VERSION = 'v1'
    GBP_TOKEN_URI = 'https://oauth2.googleapis.com/token'
    GBP_SCOPES = 'https://www.googleapis.com/auth/business.manage'
    GBP_AUTH_PROVIDER = 'https://accounts.google.com/o/oauth2/auth'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    # Clear OAuth creds for testing (mock mode)
    GOOGLE_CLIENT_ID = ''
    GOOGLE_CLIENT_SECRET = ''
