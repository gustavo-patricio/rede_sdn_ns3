"""Persistencia SQLite para snapshots de metricas de sensores."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_metrics_snapshot (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at         TEXT NOT NULL,
    tail                INTEGER NOT NULL,
    grupo               TEXT NOT NULL,
    sensor              TEXT NOT NULL,
    messages            INTEGER,
    bytes               INTEGER,
    duration_seconds    REAL,
    messages_per_second REAL,
    throughput_bps      REAL,
    avg_payload_bytes   REAL,
    avg_delay_ms        REAL,
    min_delay_ms        REAL,
    max_delay_ms        REAL,
    jitter_ms           REAL,
    expected_messages   INTEGER,
    missing_messages    INTEGER,
    packet_loss_percent REAL,
    first_seen          TEXT,
    last_seen           TEXT,
    last_sequence       INTEGER,
    origins_json        TEXT,
    last_reading_json   TEXT,
    reading_stats_json  TEXT
);

CREATE INDEX IF NOT EXISTS ix_snapshot_grupo_ts
    ON sensor_metrics_snapshot (grupo, captured_at);

CREATE INDEX IF NOT EXISTS ix_snapshot_sensor_ts
    ON sensor_metrics_snapshot (grupo, sensor, captured_at);

CREATE INDEX IF NOT EXISTS ix_snapshot_captured_at
    ON sensor_metrics_snapshot (captured_at);
"""


INSERT_SQL = """
INSERT INTO sensor_metrics_snapshot (
    captured_at, tail, grupo, sensor,
    messages, bytes, duration_seconds, messages_per_second, throughput_bps,
    avg_payload_bytes, avg_delay_ms, min_delay_ms, max_delay_ms, jitter_ms,
    expected_messages, missing_messages, packet_loss_percent,
    first_seen, last_seen, last_sequence,
    origins_json, last_reading_json, reading_stats_json
) VALUES (
    :captured_at, :tail, :grupo, :sensor,
    :messages, :bytes, :duration_seconds, :messages_per_second, :throughput_bps,
    :avg_payload_bytes, :avg_delay_ms, :min_delay_ms, :max_delay_ms, :jitter_ms,
    :expected_messages, :missing_messages, :packet_loss_percent,
    :first_seen, :last_seen, :last_sequence,
    :origins_json, :last_reading_json, :reading_stats_json
)
"""


JSON_FIELDS = (
    ("origins_json", "origins"),
    ("last_reading_json", "last_reading"),
    ("reading_stats_json", "reading_stats"),
)


ALLOWED_METRICS = (
    "messages",
    "bytes",
    "duration_seconds",
    "messages_per_second",
    "throughput_bps",
    "avg_payload_bytes",
    "avg_delay_ms",
    "min_delay_ms",
    "max_delay_ms",
    "jitter_ms",
    "expected_messages",
    "missing_messages",
    "packet_loss_percent",
    "last_sequence",
)


@contextmanager
def connect(path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        yield conn
    finally:
        conn.close()


def init_db(path: str) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def bulk_insert_snapshots(path: str, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    with connect(path) as conn:
        conn.executemany(INSERT_SQL, rows)
        conn.commit()
    return len(rows)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for json_key, target_key in JSON_FIELDS:
        raw = data.pop(json_key, None)
        try:
            data[target_key] = json.loads(raw) if raw else None
        except (TypeError, ValueError):
            data[target_key] = None
    return data


def latest_snapshots(
    path: str,
    group: str | None = None,
    sensor: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
    SELECT s.*
    FROM sensor_metrics_snapshot AS s
    JOIN (
        SELECT grupo, sensor, MAX(captured_at) AS max_ts
        FROM sensor_metrics_snapshot
        GROUP BY grupo, sensor
    ) AS latest
        ON s.grupo = latest.grupo
       AND s.sensor = latest.sensor
       AND s.captured_at = latest.max_ts
    WHERE 1 = 1
    """
    params: dict[str, Any] = {}
    if group is not None:
        sql += " AND s.grupo = :grupo"
        params["grupo"] = group
    if sensor is not None:
        sql += " AND s.sensor = :sensor"
        params["sensor"] = sensor
    sql += " ORDER BY s.grupo, s.sensor;"

    with connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_dict(row) for row in rows]


def stats(path: str) -> dict[str, Any]:
    with connect(path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)                    AS total_rows,
                   MIN(captured_at)            AS first_capture,
                   MAX(captured_at)            AS last_capture,
                   COUNT(DISTINCT grupo)       AS distinct_groups,
                   COUNT(DISTINCT sensor)      AS distinct_sensors
            FROM sensor_metrics_snapshot;
            """
        ).fetchone()
    return dict(row) if row else {
        "total_rows": 0,
        "first_capture": None,
        "last_capture": None,
        "distinct_groups": 0,
        "distinct_sensors": 0,
    }


def _filters(
    group: str | None,
    sensor: str | None,
    since: str | None,
    until: str | None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = ["1 = 1"]
    params: dict[str, Any] = {}
    if group is not None:
        clauses.append("grupo = :grupo")
        params["grupo"] = group
    if sensor is not None:
        clauses.append("sensor = :sensor")
        params["sensor"] = sensor
    if since is not None:
        clauses.append("captured_at >= :since")
        params["since"] = since
    if until is not None:
        clauses.append("captured_at <= :until")
        params["until"] = until
    return " AND ".join(clauses), params


def count_snapshots(
    path: str,
    group: str | None = None,
    sensor: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> int:
    where, params = _filters(group, sensor, since, until)
    sql = f"SELECT COUNT(*) AS total FROM sensor_metrics_snapshot WHERE {where};"
    with connect(path) as conn:
        row = conn.execute(sql, params).fetchone()
    return int(row["total"]) if row else 0


def query_snapshots(
    path: str,
    group: str | None = None,
    sensor: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
    offset: int = 0,
    order: str = "desc",
) -> list[dict[str, Any]]:
    where, params = _filters(group, sensor, since, until)
    direction = "DESC" if order.lower() == "desc" else "ASC"
    params["limit"] = limit
    params["offset"] = offset
    sql = (
        f"SELECT * FROM sensor_metrics_snapshot "
        f"WHERE {where} "
        f"ORDER BY captured_at {direction}, grupo, sensor "
        f"LIMIT :limit OFFSET :offset;"
    )
    with connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def query_series(
    path: str,
    metric: str,
    group: str | None = None,
    sensor: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    if metric not in ALLOWED_METRICS:
        raise ValueError(
            f"Metrica invalida: {metric}. Use uma de: {', '.join(ALLOWED_METRICS)}"
        )
    where, params = _filters(group, sensor, since, until)
    params["limit"] = limit
    sql = (
        f"SELECT captured_at, grupo, sensor, {metric} AS value "
        f"FROM sensor_metrics_snapshot "
        f"WHERE {where} "
        f"ORDER BY grupo, sensor, captured_at ASC "
        f"LIMIT :limit;"
    )
    with connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
