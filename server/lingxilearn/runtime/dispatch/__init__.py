"""The runtime dispatch package: one pipeline, five focused owners.

``dispatcher`` composes the pipeline (claim → resolve → execute → apply
policy → project); ``scheduler`` owns WorkItem claim/lease against the #56
work ledger; ``binding`` is the pure capability → skill → provider resolver;
``runner`` owns AgentRun/SkillRun identity and provider invocation;
``policy`` owns the outcome mapping (blocked/failed/held/completed);
``projection`` owns the canonical runtime-event emission shape.

The historical ``runtime/dispatch.py`` module became this package (issue
#60); the public import surface is unchanged.
"""

from .binding import NoProvider, Resolution, resolve
from .dispatcher import DispatchDeps, Dispatcher
from .runner import _ProviderRuntime

__all__ = [
    "DispatchDeps",
    "Dispatcher",
    "NoProvider",
    "Resolution",
    "_ProviderRuntime",
    "resolve",
]
