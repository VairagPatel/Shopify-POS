"""Shared operation failures independent of HTTP transport and database implementation."""


class GatewayError(Exception):
    # Preserve the provider status and uncertainty for safe orchestration decisions.
    def __init__(self, message, *, status_code=None, uncertain=False):
        super().__init__(message)
        self.status_code = status_code
        self.uncertain = uncertain


class StateConflict(Exception):
    """An operation cannot claim or change the current persisted state."""


class CheckoutNotFound(Exception):
    """The requested local checkout does not exist."""
