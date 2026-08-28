class IdealAPIError(Exception):
    """Base error for ideal_apis."""


class MissingAPIKeyError(IdealAPIError):
    """Raised when a keyed integration is called without credentials."""

    def __init__(self, service: str, env_var: str):
        self.service = service
        self.env_var = env_var
        super().__init__(
            f"{service} requires {env_var}. Copy ideal_apis/.env.example to .env and set the key."
        )


class APIRequestError(IdealAPIError):
    """Raised when an upstream API returns a non-success response."""

    def __init__(self, service: str, status_code: int, detail: str):
        self.service = service
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{service} HTTP {status_code}: {detail}")
