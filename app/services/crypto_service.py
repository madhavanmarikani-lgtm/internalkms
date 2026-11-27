import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _get_fernet():
    secret = current_app.config.get('SECRET_KEY', 'ai-key-manager-default-secret')
    digest = hashlib.sha256(secret.encode('utf-8')).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_value(plaintext):
    """Encrypts a string value using Fernet symmetric encryption."""
    if not plaintext:
        return None
    f = _get_fernet()
    return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_value(ciphertext):
    """Decrypts a Fernet-encrypted string. Returns original if not valid Fernet token."""
    if not ciphertext:
        return ''
    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except (InvalidToken, Exception):
        return ciphertext
