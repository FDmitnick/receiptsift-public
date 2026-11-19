import sqlite3
from datetime import UTC, datetime, timedelta

from backend.runtime_security import InMemoryRateLimiter, RuntimeMonitor, pseudonymous_subject


def test_in_memory_rate_limiter_and_subject_hashing_do_not_retain_raw_identity():
    limiter = InMemoryRateLimiter()
    subject = pseudonymous_subject("s" * 32, "login", "Owner@Example.com")

    assert "owner" not in subject
    assert limiter.check(subject, limit=2, window_seconds=60, now=100).allowed is True
    assert limiter.check(subject, limit=2, window_seconds=60, now=101).allowed is True
    blocked = limiter.check(subject, limit=2, window_seconds=60, now=102)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 58
    assert limiter.check(subject, limit=2, window_seconds=60, now=161).allowed is True


def test_runtime_monitor_persists_daily_cost_without_receipt_data(tmp_path):
    path = tmp_path / "runtime-operations.json"
    monitor = RuntimeMonitor(path)
    reservation = monitor.reserve_ai(daily_budget_usd=0.20, reserve_usd=0.15)

    assert reservation == 0.15
    monitor.complete_ai(
        reservation_usd=reservation,
        actual_cost_usd=0.10,
        model="test/model",
        input_tokens=100,
        output_tokens=20,
        elapsed_seconds=1.5,
        success=True,
    )
    monitor.record_parse(provider="atlas", elapsed_seconds=2.0, success=True, status="ready")

    reloaded = RuntimeMonitor(path).snapshot(daily_budget_usd=0.20)
    assert reloaded["estimated_ai_cost_usd"] == 0.10
    assert reloaded["daily_ai_budget_remaining_usd"] == 0.10
    assert reloaded["ai_calls"] == 1
    assert reloaded["parse_count"] == 1
    assert reloaded["contains_receipt_data"] is False
    assert RuntimeMonitor(path).reserve_ai(daily_budget_usd=0.20, reserve_usd=0.15) is None


def test_runtime_monitor_keeps_daily_and_rolling_30_day_usage(tmp_path):
    current = [datetime(2026, 8, 1, 12, tzinfo=UTC)]
    monitor = RuntimeMonitor(tmp_path / "runtime-operations.json", clock=lambda: current[0])

    first_reservation = monitor.reserve_ai(daily_budget_usd=5.0, reserve_usd=0.25)
    monitor.complete_ai(
        reservation_usd=first_reservation or 0.0,
        actual_cost_usd=0.10,
        model="openai/gpt-5.6-luna",
        input_tokens=100,
        output_tokens=20,
        elapsed_seconds=1.0,
        success=True,
    )
    monitor.record_parse(
        provider="atlas",
        elapsed_seconds=2.0,
        success=True,
        status="ready",
        processed_images=2,
    )

    current[0] += timedelta(days=1)
    second_reservation = monitor.reserve_ai(daily_budget_usd=5.0, reserve_usd=0.25)
    monitor.complete_ai(
        reservation_usd=second_reservation or 0.0,
        actual_cost_usd=0.20,
        model="openai/gpt-5.6-sol",
        input_tokens=50,
        output_tokens=10,
        elapsed_seconds=1.0,
        success=True,
    )
    monitor.record_parse(
        provider="atlas",
        elapsed_seconds=2.0,
        success=True,
        status="ready",
        processed_images=3,
    )

    usage = monitor.snapshot(daily_budget_usd=5.0)["usage_summary"]

    assert usage["today"] == {
        "date": "2026-08-02",
        "processed_images": 3,
        "input_tokens": 50,
        "output_tokens": 10,
        "total_tokens": 60,
        "estimated_cost_usd": 0.2,
        "ai_calls": 1,
    }
    assert usage["last_30_days"] == {
        "processed_images": 5,
        "input_tokens": 150,
        "output_tokens": 30,
        "total_tokens": 180,
        "estimated_cost_usd": 0.3,
        "ai_calls": 2,
    }
    assert len(usage["daily"]) == 30
    assert usage["daily"][1]["date"] == "2026-08-01"
    assert usage["daily"][1]["processed_images"] == 2
    assert usage["timezone"] == "UTC"
    assert "daily_usage_history" not in monitor.snapshot(daily_budget_usd=5.0)


def test_capacity_monitor_separates_database_worker_and_application_scaling_signals(tmp_path):
    monitor = RuntimeMonitor(tmp_path / "runtime-operations.json")

    for _ in range(3):
        monitor.record_http(
            status_code=500,
            elapsed_seconds=0.1,
            error=sqlite3.OperationalError("database is locked"),
        )
        monitor.record_batch(
            elapsed_seconds=1.0,
            queue_delay_seconds=301,
            success=False,
        )
    for _ in range(17):
        monitor.record_http(status_code=200, elapsed_seconds=0.1)

    snapshot = monitor.snapshot(daily_budget_usd=5.0, database_backend="sqlite")

    assert snapshot["sqlite_contention_errors"] == 3
    assert snapshot["http_5xx_rate"] == 0.15
    assert snapshot["batch_failure_rate"] == 1.0
    assert snapshot["capacity_assessment"]["database"]["status"] == "consider_postgresql"
    assert snapshot["capacity_assessment"]["worker"]["status"] == "scale_worker"
    assert snapshot["capacity_assessment"]["application"]["status"] == "investigate_errors"


def test_capacity_monitor_does_not_treat_generic_slow_requests_as_a_postgresql_signal(tmp_path):
    monitor = RuntimeMonitor(tmp_path / "runtime-operations.json")
    monitor.record_http(status_code=200, elapsed_seconds=3.0, slow_request_ms=2_000)

    snapshot = monitor.snapshot(daily_budget_usd=5.0, database_backend="sqlite")

    assert snapshot["slow_http_requests"] == 1
    assert snapshot["capacity_assessment"]["database"]["status"] == "sqlite_ok"
