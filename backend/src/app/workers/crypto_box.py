"""Argon2 hashing offload.

Argon2id with secure parameters is intentionally CPU- and memory-heavy. It does
not fit the 10 ms CPU budget of a normal Worker invocation, so the main Worker
calls this Durable Object instead of weakening the password parameters.
"""

from app.core.security import hash_password, verify_password
from workers import DurableObject


class CryptoBox(DurableObject):
    async def verify(self, password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)

    async def hash(self, password: str) -> str:
        return hash_password(password)
