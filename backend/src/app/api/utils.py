from fastapi import Request


def client_ip(request: Request) -> str:
    """Return the real client IP; Cloudflare sets CF-Connecting-IP."""

    forwarded = request.headers.get("CF-Connecting-IP")
    if forwarded:
        return forwarded
    if request.client is not None:
        return request.client.host
    return "unknown"


def request_env(request: Request):
    return request.scope.get("env")
