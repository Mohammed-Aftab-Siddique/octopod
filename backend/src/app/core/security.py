import hashlib
import secrets
import time
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status

_hasher = PasswordHasher()

# These are the expected "the credentials do not match" failures. Anything
# else (for example a hashing backend failure) should propagate.
_INVALID_CREDENTIAL_ERRORS = (VerifyMismatchError, VerificationError, InvalidHashError)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except _INVALID_CREDENTIAL_ERRORS:
        return False


def _crypto_binding(env):
    return getattr(env, "CRYPTO", None) if env is not None else None


async def verify_password_remote(env, password: str, password_hash: str) -> bool:
    """Verify a password in the CryptoBox Durable Object when running on Workers.

    Argon2 verification is intentionally CPU- and memory-heavy and does not fit
    the 10 ms budget of a normal Worker invocation. Local development and tests
    fall back to the in-process implementation.
    """

    binding = _crypto_binding(env)
    if binding is None:
        return verify_password(password, password_hash)
    stub = binding.get(binding.idFromName("crypto"))
    return bool(await stub.verify(password, password_hash))


async def hash_password_remote(env, password: str) -> str:
    binding = _crypto_binding(env)
    if binding is None:
        return hash_password(password)
    stub = binding.get(binding.idFromName("crypto"))
    return str(await stub.hash(password))


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RateLimiter:
    """Rate limiter backed by a Durable Object on Workers.

    Locally (and in the pytest suite) it uses an in-memory per-process store.
    The public interface is async so route handlers can always ``await`` it.
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    @staticmethod
    def _binding(env):
        return getattr(env, "RATE_LIMITER", None) if env is not None else None

    def _check_local(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        hits = [hit for hit in self._hits[key] if now - hit < window_seconds]
        if len(hits) >= limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    async def check(self, key: str, *, limit: int, window_seconds: int, env=None) -> None:
        binding = self._binding(env)
        if binding is None:
            allowed = self._check_local(key, limit=limit, window_seconds=window_seconds)
        else:
            stub = binding.get(binding.idFromName("rate-limiter"))
            allowed = bool(await stub.check(key, limit, window_seconds))
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please try again shortly.",
            )

    def reset(self) -> None:
        """Clear all recorded hits. Used by tests and local tooling."""
        self._hits.clear()


rate_limiter = RateLimiter()
