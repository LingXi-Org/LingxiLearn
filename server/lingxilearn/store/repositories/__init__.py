"""Repository modules organized by domain.

This module provides backward-compatible imports while we migrate
to domain-specific repositories.
"""

from .database import Database
from .learner import LearnerRepository
from .legacy import Repository

__all__ = ["Database", "LearnerRepository", "Repository"]