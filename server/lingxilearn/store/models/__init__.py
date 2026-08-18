"""Domain-split ORM models sharing a single ``Base.metadata``.

Import models from the domain module that owns them — e.g.
``from lingxilearn.store.models.agent import AgentTask`` — instead of a
package-wide re-export.  This keeps the import graph honest: a repository or
router only couples to the domains it actually persists.

Only the shared base and helpers are exported here.  Importing this package
deliberately does *not* register every table; use :mod:`.registry` (as the
Alembic env does) when the full metadata must be populated.
"""

from .base import Base, utcnow

__all__ = ["Base", "utcnow"]
