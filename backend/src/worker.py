"""Cloudflare Workers entrypoint for the Octopod FastAPI app."""

from workers import asgi

from app.main import app
from app.workers.crypto_box import CryptoBox
from app.workers.generator import Generator
from app.workers.rate_limiter import RateLimiter
from app.workers.renderer import Renderer

# Durable Object classes must be importable from the Worker entry module.
__all__ = ["Default", "CryptoBox", "Generator", "RateLimiter", "Renderer"]

# workers.asgi adapts the FastAPI ASGI app to the Workers fetch handler.
Default = asgi.entrypoint(app)
