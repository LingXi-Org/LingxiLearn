"""Domain errors shared across application and persistence adapters."""


class AgentTaskCreateConflict(RuntimeError):
    """A create idempotency key already owns another AgentTask."""
