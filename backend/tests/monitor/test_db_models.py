"""Tests for MonitorRule and MonitorLog SQLAlchemy models."""


def test_monitor_rule_table_exists():
    from database.models import MonitorRule
    assert MonitorRule.__tablename__ == "monitor_rules"


def test_monitor_rule_has_required_columns():
    from database.models import MonitorRule
    columns = {c.name for c in MonitorRule.__table__.columns}
    expected = {
        "id", "user_id", "name", "enabled",
        "trigger_type", "trigger_config",
        "action_type", "action_config",
        "instrument_token", "symbol",
        "linked_trade_id", "linked_order_id",
        "fire_count", "max_fires",
        "expires_at", "created_at", "updated_at", "fired_at",
    }
    assert expected.issubset(columns)


def test_monitor_log_table_exists():
    from database.models import MonitorLog
    assert MonitorLog.__tablename__ == "monitor_logs"


def test_monitor_log_has_required_columns():
    from database.models import MonitorLog
    columns = {c.name for c in MonitorLog.__table__.columns}
    expected = {"id", "user_id", "rule_id", "trigger_snapshot", "action_taken", "action_result", "created_at"}
    assert expected.issubset(columns)
