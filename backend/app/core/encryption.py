from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt(value: str) -> str:
    if not value:
        return value
    return _fernet.encrypt(value.encode()).decode()

def decrypt(value: str) -> str:
    if not value:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        return value  # ya venía en claro (migraciones antiguas)

def ya_encriptado(value: str) -> bool:
    """Los tokens Fernet siempre empiezan con 'gAAAA'."""
    return value is not None and value.startswith("gAAAA")