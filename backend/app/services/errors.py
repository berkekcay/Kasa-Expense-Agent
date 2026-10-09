"""Domain errors raised by services; the API layer maps them to HTTP status codes."""


class DomainError(Exception):
    status_code = 400


class NotFound(DomainError):
    status_code = 404


class Forbidden(DomainError):
    status_code = 403


class InvalidInput(DomainError):
    status_code = 422
