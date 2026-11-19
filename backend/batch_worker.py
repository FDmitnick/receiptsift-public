from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Any

from fastapi import HTTPException

from .batch_repository import BatchRepository
from .runtime_security import RuntimeMonitor

ProgressCallback = Callable[[str, int, str], None]
BatchProcessor = Callable[[str, bytes, str, ProgressCallback], dict[str, Any]]


def _error_code(error: Exception) -> str:
    if isinstance(error, HTTPException) and isinstance(error.detail, dict):
        return str(error.detail.get("code") or "processing_failed")[:120]
    return str(getattr(error, "code", error.__class__.__name__))[:120]


class BatchWorker:
    """Claims one queued PDF at a time and persists only the reviewable result."""

    def __init__(
        self,
        repository: BatchRepository,
        processor: BatchProcessor,
        poll_seconds: float = 1.0,
        cleanup_seconds: float = 3600.0,
        monitor: RuntimeMonitor | None = None,
        queue_delay_warning_seconds: int = 300,
    ) -> None:
        self.repository = repository
        self.processor = processor
        self.poll_seconds = max(0.05, poll_seconds)
        self.cleanup_seconds = max(60.0, cleanup_seconds)
        self.monitor = monitor
        self.queue_delay_warning_seconds = max(1, queue_delay_warning_seconds)

    @staticmethod
    def _queue_delay_seconds(document: dict[str, Any]) -> float:
        try:
            queued = datetime.fromisoformat(str(document.get("queued_at") or document.get("created_at") or ""))
            queued = queued if queued.tzinfo is not None else queued.replace(tzinfo=UTC)
            return max((datetime.now(UTC) - queued).total_seconds(), 0.0)
        except (TypeError, ValueError):
            return 0.0

    def process_one(self) -> bool:
        try:
            document = self.repository.claim_next_document()
        except Exception as error:
            if self.monitor is not None:
                self.monitor.record_database_error(error, operation="batch_claim")
            return False
        if document is None:
            return False
        started = time.perf_counter()
        queue_delay_seconds = self._queue_delay_seconds(document)

        def report_progress(stage: str, percent: int, detail: str) -> None:
            try:
                self.repository.update_progress(document["user_id"], document["id"], stage, percent, detail)
            except Exception as error:
                if self.monitor is not None:
                    self.monitor.record_database_error(error, operation="batch_progress")

        try:
            result = self.processor(
                document["user_id"],
                document.pop("source_pdf"),
                document["filename"],
                report_progress,
            )
            result.pop("preview_data_url", None)
            result["preview_url"] = None
            result["storage_mode"] = "retained_batch"
            report_progress("saving", 96, "Saving the structured result")
            self.repository.complete_document(document["user_id"], document["id"], result)
            if self.monitor is not None:
                self.monitor.record_batch(
                    elapsed_seconds=time.perf_counter() - started,
                    queue_delay_seconds=queue_delay_seconds,
                    success=True,
                    queue_delay_warning_seconds=self.queue_delay_warning_seconds,
                )
        except Exception as error:
            try:
                self.repository.fail_document(document["user_id"], document["id"], _error_code(error))
            finally:
                if self.monitor is not None:
                    self.monitor.record_batch(
                        elapsed_seconds=time.perf_counter() - started,
                        queue_delay_seconds=queue_delay_seconds,
                        success=False,
                        queue_delay_warning_seconds=self.queue_delay_warning_seconds,
                        error=error,
                    )
        return True

    def run_forever(self, stop: Event | None = None) -> None:
        stop_event = stop or Event()
        next_cleanup = 0.0
        while not stop_event.is_set():
            if time.monotonic() >= next_cleanup:
                try:
                    self.repository.purge_expired()
                    self.repository.requeue_stale_processing(datetime.now(UTC) - timedelta(minutes=15))
                except Exception:
                    pass
                next_cleanup = time.monotonic() + self.cleanup_seconds
            if not self.process_one():
                stop_event.wait(self.poll_seconds)
            else:
                time.sleep(0)
