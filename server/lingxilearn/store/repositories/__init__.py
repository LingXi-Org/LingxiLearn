"""Domain repositories, one owner per aggregate/use-case.

Each repository opens and closes its own short transactions and talks to the
shared :class:`~lingxilearn.store.database.Database` directly; repositories
never call each other — cross-aggregate coordination belongs in the
application service.  Import the repository class you need from its module;
this package deliberately re-exports nothing.
"""
