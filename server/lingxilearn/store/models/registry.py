"""Complete model registry: importing this module registers every table.

Alembic's env imports this to guarantee ``Base.metadata`` is fully populated
before autogenerate/diff.  Application code should keep importing the
individual domain modules instead.
"""

from __future__ import annotations

from . import agent, identity, learning, runtime, workspace
from .base import Base

__all__ = ["Base", "agent", "identity", "learning", "runtime", "workspace"]
