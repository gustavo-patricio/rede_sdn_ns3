"""Loop assincrono que persiste snapshots de metricas no SQLite."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

import storage


logger = logging.getLogger("ingester")


def _as_dict(collection: Any) -> dict[str, Any]:
    if hasattr(collection, "model_dump"):
        return collection.model_dump()
    if isinstance(collection, dict):
        return collection
    raise TypeError(f"snapshot precisa ser pydantic ou dict, recebido: {type(collection)!r}")


def snapshot_to_rows(collection: Any, captured_at: str, tail: int) -> list[dict[str, Any]]:
    payload = _as_dict(collection)
    rows: list[dict[str, Any]] = []
    groups = payload.get("groups", {}) or {}
    for grupo, sensors in groups.items():
        if not sensors:
            continue
        for sensor, metrics in sensors.items():
            rows.append(
                {
                    "captured_at": captured_at,
                    "tail": tail,
                    "grupo": grupo,
                    "sensor": sensor,
                    "messages": metrics.get("messages"),
                    "bytes": metrics.get("bytes"),
                    "duration_seconds": metrics.get("duration_seconds"),
                    "messages_per_second": metrics.get("messages_per_second"),
                    "throughput_bps": metrics.get("throughput_bps"),
                    "avg_payload_bytes": metrics.get("avg_payload_bytes"),
                    "avg_delay_ms": metrics.get("avg_delay_ms"),
                    "min_delay_ms": metrics.get("min_delay_ms"),
                    "max_delay_ms": metrics.get("max_delay_ms"),
                    "jitter_ms": metrics.get("jitter_ms"),
                    "expected_messages": metrics.get("expected_messages"),
                    "missing_messages": metrics.get("missing_messages"),
                    "packet_loss_percent": metrics.get("packet_loss_percent"),
                    "first_seen": metrics.get("first_seen"),
                    "last_seen": metrics.get("last_seen"),
                    "last_sequence": metrics.get("last_sequence"),
                    "origins_json": json.dumps(metrics.get("origins") or []),
                    "last_reading_json": json.dumps(metrics.get("last_reading") or {}),
                    "reading_stats_json": json.dumps(metrics.get("reading_stats") or {}),
                }
            )
    return rows


async def ingest_once(
    snapshot_fn: Callable[[int], Any],
    db_path: str,
    tail: int,
) -> int:
    collection = await asyncio.to_thread(snapshot_fn, tail)
    captured_at = datetime.now(timezone.utc).isoformat()
    rows = snapshot_to_rows(collection, captured_at, tail)
    return await asyncio.to_thread(storage.bulk_insert_snapshots, db_path, rows)


async def ingest_loop(
    snapshot_fn: Callable[[int], Any],
    db_path: str,
    tail: int,
    interval_s: float,
    stop_event: asyncio.Event,
) -> None:
    logger.info(
        "ingester iniciado: db=%s interval=%ss tail=%s", db_path, interval_s, tail
    )
    while not stop_event.is_set():
        try:
            inserted = await ingest_once(snapshot_fn, db_path, tail)
            if inserted:
                logger.info("ingest ok: inseridos=%s", inserted)
            else:
                logger.debug("ingest sem dados: nenhum sensor com metricas")
        except Exception as exc:  # noqa: BLE001
            logger.warning("ingest falhou: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            continue

    logger.info("ingester encerrado")
