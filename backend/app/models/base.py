"""Shared declarative base. No tables yet — Phase 0 is infrastructure only.

Later phases define ORM models here (or in sibling modules that import this
Base) so Alembic's autogenerate can discover them via target_metadata in
alembic/env.py.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
