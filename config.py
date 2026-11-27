import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ai-key-manager-super-secure-key-2026-prod-fallback')
    
    # SQLite Database location: backend/instance or instance/
    INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f"sqlite:///{os.path.join(INSTANCE_DIR, 'ai_key_manager.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # Application Info
    APP_NAME = "AI Key Manager"
    APP_VERSION = "1.0.0"

    # SMTP Email Configuration (loaded strictly from .env / environment)
    SMTP_HOST = os.environ.get('SMTP_HOST', '')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL', os.environ.get('SMTP_USER', ''))
    ALERT_RECIPIENT_EMAILS = os.environ.get('ALERT_RECIPIENT_EMAILS', '')
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:5001')
    DATABASE_ACCESS_PASSWORD = os.environ.get('DATABASE_ACCESS_PASSWORD', 'DbAdmin@2026')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SMTP_HOST = ''
    SMTP_USER = ''
    SMTP_PASSWORD = ''
    ALERT_RECIPIENT_EMAILS = ''

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
