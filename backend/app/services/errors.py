"""Domain errors raised by services; the API layer maps them to HTTP status codes."""


class DomainError(Exception):
    status_code = 400


class NotFound(DomainError):
    status_code = 404


class Forbidden(DomainError):
    status_code = 403


class Conflict(DomainError):
    """E.g. an import that was already saved (same owner + source + external_ref)."""

    status_code = 409


class InvalidInput(DomainError):
    status_code = 422


class NotConfigured(DomainError):
    """A feature needs settings that are missing (OAuth client, encryption key...)."""

    status_code = 503


class UpstreamError(DomainError):
    """A Google / TCMB call failed."""

    status_code = 502


class BadRequest(DomainError):
    """The request is well formed but cannot be accepted (weak password, wrong 2FA code)."""

    status_code = 400


class Unauthenticated(DomainError):
    """Wrong email or password, or a login step that expired."""

    status_code = 401


class Locked(DomainError):
    """Too many failed sign-in attempts; try again later."""

    status_code = 423
