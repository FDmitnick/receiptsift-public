from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("uvicorn.error")

SQLITE_CONTENTION_MARKERS = ("database is locked", "database table is locked", "database is busy")


def is_sqlite_contention_error(error: BaseException | None) -> bool:
    """Recognize SQLite write contention without recording SQL or user data."""
    current = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, sqlite3.OperationalError):
            message = str(current).casefold()
            if any(marker in message for marker in SQLITE_CONTENTION_MARKERS):
                return True
        current = current.__cause__ or current.__context__
    return False


def structured_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """Write a privacy-minimized JSON event to Railway's existing stdout logs."""
    payload: dict[str, Any] = {
        "event": event[:64],
        "timestamp": datetime.now(UTC).isoformat(),
    }
    for key, value in fields.items():
        if value is None or isinstance(value, (bool, int, float)):
            payload[str(key)[:48]] = value
        elif isinstance(value, str):
            payload[str(key)[:48]] = value.replace("\r", " ").replace("\n", " ")[:240]
        elif isinstance(value, (list, tuple)):
            payload[str(key)[:48]] = [str(item)[:80] for item in list(value)[:20]]
    LOGGER.log(level, json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def pseudonymous_subject(secret: str, namespace: str, value: str) -> str:
    key = hashlib.sha256((secret or "receiptsift-runtime-limit").encode()).digest()
    message = f"{namespace.strip().casefold()}:{value.strip().casefold()}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int


class InMemoryRateLimiter:
    """Single-replica limiter with no database schema or external service."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> RateLimitDecision:
        current = time.monotonic() if now is None else now
        window = max(int(window_seconds), 1)
        maximum = max(int(limit), 1)
        cutoff = current - window
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= maximum:
                retry_after = max(int(events[0] + window - current), 1)
                return RateLimitDecision(False, retry_after)
            events.append(current)
            if len(self._events) > 10_000:
                self._events = {item_key: values for item_key, values in self._events.items() if values}
        return RateLimitDecision(True, 0)


class RuntimeMonitor:
    """Persistent aggregate metrics and a restart-safe daily AI spend guard.

    State is one small JSON file on the existing Railway volume. It contains no
    receipt content, filenames, email addresses, user IDs, or network addresses.
    """

    HISTORY_RETENTION_DAYS = 90

    def __init__(self, path: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    @staticmethod
    def _empty_state(day: str) -> dict[str, Any]:
        return {
            "date": day,
            "estimated_ai_cost_usd": 0.0,
            "ai_calls": 0,
            "ai_failures": 0,
            "gpt_verifier_calls": 0,
            "gpt_verifier_failures": 0,
            "provider_input_tokens": 0,
            "provider_output_tokens": 0,
            "processed_images": 0,
            "parse_count": 0,
            "parse_failures": 0,
            "parse_elapsed_seconds_total": 0.0,
            "http_requests": 0,
            "http_5xx": 0,
            "slow_http_requests": 0,
            "sqlite_contention_errors": 0,
            "batch_jobs": 0,
            "batch_failures": 0,
            "batch_elapsed_seconds_total": 0.0,
            "batch_queue_delay_breaches": 0,
            "last_capacity_event": None,
            "last_capacity_event_at": None,
            "last_provider_model": None,
            "last_provider_event_at": None,
            "daily_usage_history": {},
        }

    @staticmethod
    def _usage_bucket(state: dict[str, Any], day: str) -> dict[str, Any]:
        input_tokens = max(int(state.get("provider_input_tokens") or 0), 0)
        output_tokens = max(int(state.get("provider_output_tokens") or 0), 0)
        return {
            "date": day,
            "processed_images": max(int(state.get("processed_images") or 0), 0),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost_usd": round(max(float(state.get("estimated_ai_cost_usd") or 0.0), 0.0), 6),
            "ai_calls": max(int(state.get("ai_calls") or 0), 0),
        }

    def _normalized_history(self, raw: Any) -> dict[str, dict[str, Any]]:
        today = self._now().date()
        cutoff = today - timedelta(days=self.HISTORY_RETENTION_DAYS - 1)
        history: dict[str, dict[str, Any]] = {}
        if not isinstance(raw, dict):
            return history
        for day, bucket in raw.items():
            try:
                parsed_day = datetime.strptime(str(day), "%Y-%m-%d").date()
            except ValueError:
                continue
            if parsed_day < cutoff or parsed_day > today or not isinstance(bucket, dict):
                continue
            input_tokens = max(int(bucket.get("input_tokens") or 0), 0)
            output_tokens = max(int(bucket.get("output_tokens") or 0), 0)
            history[parsed_day.isoformat()] = {
                "date": parsed_day.isoformat(),
                "processed_images": max(int(bucket.get("processed_images") or 0), 0),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "estimated_cost_usd": round(max(float(bucket.get("estimated_cost_usd") or 0.0), 0.0), 6),
                "ai_calls": max(int(bucket.get("ai_calls") or 0), 0),
            }
        return history

    def _sync_usage_history(self, state: dict[str, Any]) -> None:
        history = self._normalized_history(state.get("daily_usage_history"))
        day = str(state.get("date") or self._now().date().isoformat())
        history[day] = self._usage_bucket(state, day)
        state["daily_usage_history"] = self._normalized_history(history)

    def _load_locked(self) -> dict[str, Any]:
        day = self._now().date().isoformat()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty_state(day)
        if not isinstance(payload, dict):
            return self._empty_state(day)
        payload_day = str(payload.get("date") or "")
        prior = self._empty_state(payload_day or day)
        for key in prior:
            if key in payload:
                prior[key] = payload[key]
        history = self._normalized_history(payload.get("daily_usage_history"))
        if payload_day:
            history[payload_day] = self._usage_bucket(prior, payload_day)
        state = prior if payload_day == day else self._empty_state(day)
        state["daily_usage_history"] = history
        self._sync_usage_history(state)
        return state

    def _save_locked(self, state: dict[str, Any]) -> None:
        try:
            self._sync_usage_history(state)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError as error:
            structured_event("runtime_metrics_write_failed", level=logging.ERROR, error_type=type(error).__name__)

    def reserve_ai(self, *, daily_budget_usd: float, reserve_usd: float) -> float | None:
        budget = max(float(daily_budget_usd), 0.0)
        reserve = max(float(reserve_usd), 0.0)
        with self._lock:
            state = self._load_locked()
            current = float(state["estimated_ai_cost_usd"] or 0.0)
            if budget <= 0 or current + reserve > budget:
                return None
            state["estimated_ai_cost_usd"] = round(current + reserve, 6)
            self._save_locked(state)
        return reserve

    def complete_ai(
        self,
        *,
        reservation_usd: float,
        actual_cost_usd: float,
        model: str,
        input_tokens: int,
        output_tokens: int,
        elapsed_seconds: float,
        success: bool,
        verifier: bool = False,
    ) -> None:
        with self._lock:
            state = self._load_locked()
            current = float(state["estimated_ai_cost_usd"] or 0.0)
            state["estimated_ai_cost_usd"] = round(
                max(0.0, current - max(reservation_usd, 0.0) + max(actual_cost_usd, 0.0)),
                6,
            )
            state["ai_calls"] = int(state["ai_calls"] or 0) + 1
            state["ai_failures"] = int(state["ai_failures"] or 0) + (0 if success else 1)
            if verifier:
                state["gpt_verifier_calls"] = int(state["gpt_verifier_calls"] or 0) + 1
                state["gpt_verifier_failures"] = int(state["gpt_verifier_failures"] or 0) + (0 if success else 1)
            state["provider_input_tokens"] = int(state["provider_input_tokens"] or 0) + max(input_tokens, 0)
            state["provider_output_tokens"] = int(state["provider_output_tokens"] or 0) + max(output_tokens, 0)
            state["last_provider_model"] = model[:160]
            state["last_provider_event_at"] = self._now().isoformat()
            self._save_locked(state)
        structured_event(
            "provider_call",
            model=model,
            verifier=verifier,
            success=success,
            elapsed_ms=round(max(elapsed_seconds, 0.0) * 1000),
            input_tokens=max(input_tokens, 0),
            output_tokens=max(output_tokens, 0),
            estimated_cost_usd=round(max(actual_cost_usd, 0.0), 6),
        )

    def release_ai_reservation(self, reservation_usd: float) -> None:
        with self._lock:
            state = self._load_locked()
            current = float(state["estimated_ai_cost_usd"] or 0.0)
            state["estimated_ai_cost_usd"] = round(max(0.0, current - max(reservation_usd, 0.0)), 6)
            self._save_locked(state)

    def record_parse(
        self,
        *,
        provider: str,
        elapsed_seconds: float,
        success: bool,
        status: str,
        processed_images: int = 0,
    ) -> None:
        with self._lock:
            state = self._load_locked()
            state["parse_count"] = int(state["parse_count"] or 0) + 1
            state["parse_failures"] = int(state["parse_failures"] or 0) + (0 if success else 1)
            state["processed_images"] = int(state["processed_images"] or 0) + (max(int(processed_images), 0) if success else 0)
            state["parse_elapsed_seconds_total"] = round(
                float(state["parse_elapsed_seconds_total"] or 0.0) + max(elapsed_seconds, 0.0),
                3,
            )
            self._save_locked(state)
        structured_event(
            "document_parse",
            provider=provider,
            success=success,
            status=status,
            elapsed_ms=round(max(elapsed_seconds, 0.0) * 1000),
        )

    def _record_sqlite_contention_locked(self, state: dict[str, Any], error: BaseException | None) -> bool:
        if not is_sqlite_contention_error(error):
            return False
        state["sqlite_contention_errors"] = int(state["sqlite_contention_errors"] or 0) + 1
        state["last_capacity_event"] = "sqlite_contention"
        state["last_capacity_event_at"] = self._now().isoformat()
        return True

    def record_http(
        self,
        *,
        status_code: int,
        elapsed_seconds: float,
        slow_request_ms: int = 2_000,
        error: BaseException | None = None,
    ) -> None:
        elapsed_ms = round(max(elapsed_seconds, 0.0) * 1000)
        with self._lock:
            state = self._load_locked()
            state["http_requests"] = int(state["http_requests"] or 0) + 1
            state["http_5xx"] = int(state["http_5xx"] or 0) + (1 if status_code >= 500 else 0)
            is_slow = elapsed_ms >= max(int(slow_request_ms), 1)
            state["slow_http_requests"] = int(state["slow_http_requests"] or 0) + (1 if is_slow else 0)
            contention = self._record_sqlite_contention_locked(state, error)
            self._save_locked(state)
        if contention:
            structured_event(
                "sqlite_contention",
                level=logging.ERROR,
                operation="http_request",
                status_code=status_code,
                elapsed_ms=elapsed_ms,
            )
        elif status_code >= 500:
            structured_event("capacity_http_5xx", level=logging.ERROR, status_code=status_code, elapsed_ms=elapsed_ms)
        elif is_slow:
            structured_event("slow_http_request", level=logging.WARNING, status_code=status_code, elapsed_ms=elapsed_ms)

    def record_database_error(self, error: BaseException, *, operation: str) -> None:
        with self._lock:
            state = self._load_locked()
            contention = self._record_sqlite_contention_locked(state, error)
            if contention:
                self._save_locked(state)
        if contention:
            structured_event("sqlite_contention", level=logging.ERROR, operation=operation)

    def record_batch(
        self,
        *,
        elapsed_seconds: float,
        queue_delay_seconds: float,
        success: bool,
        queue_delay_warning_seconds: int = 300,
        error: BaseException | None = None,
    ) -> None:
        elapsed = max(elapsed_seconds, 0.0)
        queue_delay = max(queue_delay_seconds, 0.0)
        with self._lock:
            state = self._load_locked()
            state["batch_jobs"] = int(state["batch_jobs"] or 0) + 1
            state["batch_failures"] = int(state["batch_failures"] or 0) + (0 if success else 1)
            state["batch_elapsed_seconds_total"] = round(
                float(state["batch_elapsed_seconds_total"] or 0.0) + elapsed,
                3,
            )
            delayed = queue_delay >= max(int(queue_delay_warning_seconds), 1)
            state["batch_queue_delay_breaches"] = int(state["batch_queue_delay_breaches"] or 0) + (1 if delayed else 0)
            contention = self._record_sqlite_contention_locked(state, error)
            if delayed:
                state["last_capacity_event"] = "batch_queue_delay"
                state["last_capacity_event_at"] = self._now().isoformat()
            self._save_locked(state)
        structured_event(
            "batch_job",
            level=logging.INFO if success else logging.ERROR,
            success=success,
            elapsed_ms=round(elapsed * 1000),
            queue_delay_ms=round(queue_delay * 1000),
        )
        if contention:
            structured_event("sqlite_contention", level=logging.ERROR, operation="batch_job")
        if delayed:
            structured_event(
                "batch_queue_delay",
                level=logging.WARNING,
                queue_delay_ms=round(queue_delay * 1000),
            )

    def snapshot(
        self,
        *,
        daily_budget_usd: float,
        database_backend: str = "sqlite",
        sqlite_contention_threshold: int = 3,
        http_error_rate_threshold: float = 0.05,
        minimum_http_sample: int = 20,
        queue_delay_breach_threshold: int = 3,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load_locked()
        usage_history = state.get("daily_usage_history") if isinstance(state.get("daily_usage_history"), dict) else {}
        daily_usage: list[dict[str, Any]] = []
        today = self._now().date()
        for offset in range(30):
            day = (today - timedelta(days=offset)).isoformat()
            daily_usage.append(
                usage_history.get(day)
                or {
                    "date": day,
                    "processed_images": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "ai_calls": 0,
                }
            )
        usage_30_days = {
            "processed_images": sum(int(item["processed_images"]) for item in daily_usage),
            "input_tokens": sum(int(item["input_tokens"]) for item in daily_usage),
            "output_tokens": sum(int(item["output_tokens"]) for item in daily_usage),
            "total_tokens": sum(int(item["total_tokens"]) for item in daily_usage),
            "estimated_cost_usd": round(sum(float(item["estimated_cost_usd"]) for item in daily_usage), 6),
            "ai_calls": sum(int(item["ai_calls"]) for item in daily_usage),
        }
        public_state = {key: value for key, value in state.items() if key != "daily_usage_history"}
        cost = float(state["estimated_ai_cost_usd"] or 0.0)
        parses = int(state["parse_count"] or 0)
        ai_calls = int(state["ai_calls"] or 0)
        verifier_calls = int(state["gpt_verifier_calls"] or 0)
        http_requests = int(state["http_requests"] or 0)
        http_5xx = int(state["http_5xx"] or 0)
        batch_jobs = int(state["batch_jobs"] or 0)
        batch_failures = int(state["batch_failures"] or 0)
        sqlite_contention = int(state["sqlite_contention_errors"] or 0)
        queue_delay_breaches = int(state["batch_queue_delay_breaches"] or 0)
        http_5xx_rate = http_5xx / http_requests if http_requests else 0.0
        database_status = "postgresql_in_use" if database_backend == "postgresql" else "sqlite_ok"
        database_reasons: list[str] = []
        if database_backend == "sqlite" and sqlite_contention:
            database_status = "consider_postgresql" if sqlite_contention >= sqlite_contention_threshold else "watch_sqlite"
            database_reasons.append(f"{sqlite_contention} SQLite lock/busy errors today")
        worker_status = "worker_ok"
        worker_reasons: list[str] = []
        if queue_delay_breaches >= queue_delay_breach_threshold:
            worker_status = "scale_worker"
            worker_reasons.append(f"{queue_delay_breaches} jobs waited beyond the queue-delay threshold")
        application_status = "application_ok"
        application_reasons: list[str] = []
        if http_requests >= minimum_http_sample and http_5xx_rate >= http_error_rate_threshold:
            application_status = "investigate_errors"
            application_reasons.append(f"HTTP 5xx rate is {http_5xx_rate:.1%}")
        return {
            **public_state,
            "usage_summary": {
                "today": daily_usage[0],
                "last_30_days": usage_30_days,
                "daily": daily_usage,
                "timezone": "UTC",
                "processed_images_definition": "successfully processed PDF page images",
            },
            "daily_ai_budget_usd": round(max(float(daily_budget_usd), 0.0), 2),
            "daily_ai_budget_remaining_usd": round(max(float(daily_budget_usd) - cost, 0.0), 6),
            "mean_parse_elapsed_seconds": round(
                float(state["parse_elapsed_seconds_total"] or 0.0) / parses,
                3,
            )
            if parses
            else 0.0,
            "ai_failure_rate": round(int(state["ai_failures"] or 0) / ai_calls, 4) if ai_calls else 0.0,
            "gpt_verifier_failure_rate": round(
                int(state["gpt_verifier_failures"] or 0) / verifier_calls,
                4,
            )
            if verifier_calls
            else 0.0,
            "http_5xx_rate": round(http_5xx_rate, 4),
            "batch_failure_rate": round(batch_failures / batch_jobs, 4) if batch_jobs else 0.0,
            "mean_batch_elapsed_seconds": round(
                float(state["batch_elapsed_seconds_total"] or 0.0) / batch_jobs,
                3,
            )
            if batch_jobs
            else 0.0,
            "capacity_assessment": {
                "database": {"status": database_status, "reasons": database_reasons},
                "worker": {"status": worker_status, "reasons": worker_reasons},
                "application": {"status": application_status, "reasons": application_reasons},
                "decision_rule": "Migrate to PostgreSQL for repeated SQLite contention; scale the worker for queue delay.",
            },
            "storage": "existing_volume_json",
            "contains_receipt_data": False,
        }
