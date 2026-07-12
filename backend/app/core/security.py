from pwdlib import PasswordHash


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Convert a plain password into a secure password hash."""

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check whether a plain password matches a stored hash."""

    return password_hasher.verify(password, password_hash)