from __future__ import annotations

import signal
from datetime import UTC, datetime, timedelta
from threading import Event

from backend.batch_worker import BatchWorker
from backend.server import _parse_with_reserved_quota, batch_repository, runtime_monitor, settings


def main() -> None:
    if not batch_repository.configured:
        raise SystemExit("Batch storage is not configured. Set RECEIPTSIFT_BATCH_ENCRYPTION_KEY.")
    stop = Event()

    def request_stop(*_: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    batch_repository.requeue_stale_processing(older_than=datetime.now(UTC) - timedelta(minutes=15))
    BatchWorker(
        batch_repository,
        _parse_with_reserved_quota,
        poll_seconds=settings.batch_worker_poll_seconds,
        monitor=runtime_monitor,
        queue_delay_warning_seconds=settings.batch_queue_delay_warning_seconds,
    ).run_forever(stop)


if __name__ == "__main__":
    main()
