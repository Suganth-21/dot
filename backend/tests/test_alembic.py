"""Alembic must be wired to the app's declarative metadata so later phases'
models are auto-discoverable (ARCHITECTURE.md §1, BUILDPHASES.md Phase 0 §4).

Running an actual `alembic upgrade head` against a live PostgreSQL database
is a separate manual verification step, not a unit test — it mutates real
database state and belongs outside the pytest suite. See the Phase 0
completion report for that command and its output.
"""
from pathlib import Path

from alembic.config import Config

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_ini_loads():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    assert cfg.get_main_option("script_location") == "alembic"


def test_target_metadata_is_wired_to_app_models():
    from app.models import Base

    assert Base.metadata is not None
    # Phase 1 adds the auth/entity tables (users, refresh_tokens, and the
    # seven reference tables) — see ARCHITECTURE.md §4.1, §4.2. Phase 2
    # adds the batch ledger and its append-only event log — §4.3, §4.4, §4.9.
    # Phase 3 adds alerts/patient_reports — §4.7, §4.9. Phase 4 adds
    # returns/notifications — §4.5, §4.8.
    expected = {
        "users", "refresh_tokens", "pharmacies", "distributors",
        "manufacturers", "facilities", "regulators", "agents", "vehicles", "drugs",
        "batches", "events", "sales",
        "alerts", "patient_reports",
        "returns", "notifications",
    }
    assert expected.issubset(set(Base.metadata.tables))
