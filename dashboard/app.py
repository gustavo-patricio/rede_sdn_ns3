#!/usr/bin/env python3
"""API REST para operar e diagnosticar o ambiente SDN/NFV local."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import docker
from docker.errors import DockerException, NotFound
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

import ingester
import storage


PROJECT_NAME = os.getenv("COMPOSE_PROJECT_NAME", "atividad_6")
SERVER_IP = os.getenv("SERVER_IP", "10.0.100.10")

METRICS_DB_PATH = os.getenv("METRICS_DB_PATH", "/data/metrics.db")
INGEST_INTERVAL_S = float(os.getenv("INGEST_INTERVAL_S", "30"))
INGEST_TAIL = int(os.getenv("INGEST_TAIL", "1000"))
INGEST_ENABLED = os.getenv("INGEST_ENABLED", "true").lower() not in {"false", "0", "no", "off"}

logger = logging.getLogger("dashboard")

GATEWAYS = {
    "uti": "gw-uti",
    "enfermaria": "gw-enfermaria",
    "triagem": "gw-triagem",
}

SENSORS = {
    "uti": ["sensor-uti-1", "sensor-uti-2", "sensor-uti-3"],
    "enfermaria": [
        "sensor-enfermaria-1",
        "sensor-enfermaria-2",
        "sensor-enfermaria-3",
    ],
    "triagem": ["sensor-triagem-1", "sensor-triagem-2", "sensor-triagem-3"],
}

ALL_SENSORS = [sensor for group in SENSORS.values() for sensor in group]

SENSOR_GROUP = {sensor: group for group, sensors in SENSORS.items() for sensor in sensors}

SENSOR_CONTROL_FILE = "/tmp/sensor_control.json"

POLICY_ENDPOINTS = {
    "enfermaria_limit": {
        "key": "enfermaria_limit",
        "method": "POST",
        "path": "/policies/enfermaria/limit",
        "group": "enfermaria",
        "action": "limit",
        "description": "Aplica limitacao de banda no gateway da enfermaria.",
        "request_body_required": False,
        "request_body_schema": None,
        "request_example": None,
        "response_model": "CommandResult",
        "status_endpoint": "/gateways",
    },
    "enfermaria_restore": {
        "key": "enfermaria_restore",
        "method": "POST",
        "path": "/policies/enfermaria/restore",
        "group": "enfermaria",
        "action": "restore",
        "description": "Remove a limitacao de banda do gateway da enfermaria.",
        "request_body_required": False,
        "request_body_schema": None,
        "request_example": None,
        "response_model": "CommandResult",
        "status_endpoint": "/gateways",
    },
    "triagem_block": {
        "key": "triagem_block",
        "method": "POST",
        "path": "/policies/triagem/block",
        "group": "triagem",
        "action": "block",
        "description": "Bloqueia o trafego da triagem para o servidor hospitalar.",
        "request_body_required": False,
        "request_body_schema": None,
        "request_example": None,
        "response_model": "CommandResult",
        "status_endpoint": "/gateways",
    },
    "triagem_unblock": {
        "key": "triagem_unblock",
        "method": "POST",
        "path": "/policies/triagem/unblock",
        "group": "triagem",
        "action": "unblock",
        "description": "Remove o bloqueio do trafego da triagem.",
        "request_body_required": False,
        "request_body_schema": None,
        "request_example": None,
        "response_model": "CommandResult",
        "status_endpoint": "/gateways",
    },
    "restore_all": {
        "key": "restore_all",
        "method": "POST",
        "path": "/policies/restore",
        "group": None,
        "action": "restore_all",
        "description": "Restaura todas as politicas dinamicas aplicadas pela API.",
        "request_body_required": False,
        "request_body_schema": None,
        "request_example": None,
        "response_model": "dict[str, CommandResult]",
        "status_endpoint": "/gateways",
    },
}

SERVER_LOG_PATTERN = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\] \[HOSPITAL\] "
    r"grupo=(?P<group>\S+) sensor=(?P<sensor>\S+) seq=(?P<sequence>\d+) "
    r"origem=(?P<origin>\S+)"
    r"(?: bytes=(?P<bytes>\d+))?"
    r"(?: delay_ms=(?P<delay_ms>[0-9.]+))?"
)


class CommandResult(BaseModel):
    container: str
    command: list[str]
    exit_code: int
    output: str


class GroupMetrics(BaseModel):
    group: str
    messages: int
    bytes: int
    duration_seconds: float
    messages_per_second: float
    throughput_bps: float
    avg_delay_ms: float | None
    jitter_ms: float | None
    expected_messages: int
    missing_messages: int
    packet_loss_percent: float


class ReadingFieldStats(BaseModel):
    samples: int
    min: float | int | None
    max: float | int | None
    avg: float | None
    last: float | int | str | None


class SensorMetrics(BaseModel):
    group: str
    sensor: str
    origins: list[str]
    messages: int
    bytes: int
    duration_seconds: float
    messages_per_second: float
    throughput_bps: float
    avg_payload_bytes: float
    avg_delay_ms: float | None
    min_delay_ms: float | None
    max_delay_ms: float | None
    jitter_ms: float | None
    expected_messages: int
    missing_messages: int
    packet_loss_percent: float
    first_seen: str | None
    last_seen: str | None
    last_sequence: int | None
    last_reading: dict[str, float | int | str]
    reading_stats: dict[str, ReadingFieldStats]


class SensorMetricsCollection(BaseModel):
    source: str
    parsed_lines: int
    ignored_lines: int
    groups: dict[str, dict[str, SensorMetrics]]


class TrafficMetrics(BaseModel):
    source: str
    parsed_lines: int
    ignored_lines: int
    groups: dict[str, GroupMetrics]


class GroupInfo(BaseModel):
    group: str
    gateway: str
    sensors: list[str]


class GroupRoutes(BaseModel):
    group: str
    gateway: CommandResult
    sensors: dict[str, CommandResult]


class GatewayPolicyStatus(BaseModel):
    bandwidth_limit_active: bool
    triage_block_active: bool
    network_emulation_active: bool


class TbfRequest(BaseModel):
    rate: str = Field(default="256kbit", description="Taxa maxima, ex.: 256kbit, 1mbit.")
    burst: str = Field(default="32kbit", description="Burst permitido, ex.: 32kbit.")
    latency: str = Field(default="400ms", description="Latencia maxima na fila, ex.: 400ms.")


class NetemRequest(BaseModel):
    delay_ms: float = Field(default=0, ge=0, description="Latencia adicional em milissegundos.")
    jitter_ms: float = Field(default=0, ge=0, description="Variacao da latencia em milissegundos.")
    loss_pct: float = Field(default=0, ge=0, le=100, description="Percentual de perda de pacotes.")
    duplicate_pct: float = Field(default=0, ge=0, le=100, description="Percentual de duplicacao.")
    corrupt_pct: float = Field(default=0, ge=0, le=100, description="Percentual de corrupcao.")
    reorder_pct: float = Field(default=0, ge=0, le=100, description="Percentual de reordenacao.")


class SensorControl(BaseModel):
    interval: float | None = Field(default=None, gt=0, description="Intervalo em segundos entre envios.")
    payload_padding_bytes: int | None = Field(default=None, ge=0, description="Bytes extras de padding no payload.")
    enabled: bool | None = Field(default=None, description="Liga ou desliga o envio sem matar o container.")


class SensorControlState(BaseModel):
    sensor: str
    group: str | None
    container_status: str
    control: dict[str, Any]


class SensorMetricsSnapshot(BaseModel):
    id: int
    captured_at: str
    tail: int
    grupo: str
    sensor: str
    messages: int | None
    bytes: int | None
    duration_seconds: float | None
    messages_per_second: float | None
    throughput_bps: float | None
    avg_payload_bytes: float | None
    avg_delay_ms: float | None
    min_delay_ms: float | None
    max_delay_ms: float | None
    jitter_ms: float | None
    expected_messages: int | None
    missing_messages: int | None
    packet_loss_percent: float | None
    first_seen: str | None
    last_seen: str | None
    last_sequence: int | None
    origins: list[str] | None
    last_reading: dict[str, Any] | None
    reading_stats: dict[str, Any] | None


class TimeseriesStats(BaseModel):
    db_path: str
    ingest_enabled: bool
    ingest_interval_s: float
    ingest_tail: int
    total_rows: int
    first_capture: str | None
    last_capture: str | None
    distinct_groups: int
    distinct_sensors: int


class PaginatedSnapshots(BaseModel):
    total: int
    limit: int
    offset: int
    order: str
    items: list[SensorMetricsSnapshot]


class SeriesPoint(BaseModel):
    t: str
    v: float | int | None


class SensorSeries(BaseModel):
    group: str
    sensor: str
    points: list[SeriesPoint]


class TimeseriesSeries(BaseModel):
    metric: str
    since: str | None
    until: str | None
    series: list[SensorSeries]


class GatewayStatus(BaseModel):
    group: str
    container: str
    docker_status: str
    running: bool
    image: str | None
    id: str | None
    ip_forward: str | None
    interfaces: str | None
    tc_eth1: str | None
    policies: GatewayPolicyStatus


class PolicyEndpoint(BaseModel):
    key: str
    method: str
    path: str
    group: str | None
    action: str
    description: str
    request_body_required: bool
    request_body_schema: dict[str, Any] | None
    request_example: dict[str, Any] | None
    response_model: str
    status_endpoint: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    task: asyncio.Task | None = None

    if INGEST_ENABLED:
        try:
            await asyncio.to_thread(storage.init_db, METRICS_DB_PATH)
            task = asyncio.create_task(
                ingester.ingest_loop(
                    snapshot_fn=calculate_sensor_metrics_collection,
                    db_path=METRICS_DB_PATH,
                    tail=INGEST_TAIL,
                    interval_s=INGEST_INTERVAL_S,
                    stop_event=stop_event,
                )
            )
            logger.info(
                "persistencia ativa: db=%s interval=%ss tail=%s",
                METRICS_DB_PATH,
                INGEST_INTERVAL_S,
                INGEST_TAIL,
            )
        except Exception as exc:
            logger.warning("persistencia desativada: %s", exc)
    else:
        logger.info("persistencia desativada por INGEST_ENABLED=false")

    try:
        yield
    finally:
        stop_event.set()
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()


app = FastAPI(
    title="API SDN/NFV - Rede Hospitalar IoMT",
    description="API local para diagnosticar containers e aplicar politicas VNF.",
    version="0.1.0",
    lifespan=lifespan,
)


def docker_client() -> docker.DockerClient:
    try:
        return docker.from_env()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail=f"Docker indisponivel: {exc}") from exc


def get_container(name: str):
    try:
        return docker_client().containers.get(name)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=f"Container nao encontrado: {name}") from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail=f"Erro ao acessar Docker: {exc}") from exc


def compose_containers() -> list:
    try:
        return docker_client().containers.list(
            all=True,
            filters={"label": f"com.docker.compose.project={PROJECT_NAME}"},
        )
    except DockerException as exc:
        raise HTTPException(status_code=503, detail=f"Erro ao listar containers: {exc}") from exc


def container_summary(container) -> dict[str, Any]:
    labels = container.labels or {}
    return {
        "name": container.name,
        "service": labels.get("com.docker.compose.service"),
        "status": container.status,
        "image": container.image.tags[0] if container.image.tags else container.image.short_id,
        "id": container.short_id,
    }


def exec_in_container(container_name: str, command: list[str]) -> CommandResult:
    container = get_container(container_name)
    result = container.exec_run(command, stdout=True, stderr=True)
    output = result.output.decode("utf-8", errors="replace")
    return CommandResult(
        container=container_name,
        command=command,
        exit_code=result.exit_code,
        output=output,
    )


def exec_output_or_none(container_name: str, command: list[str]) -> str | None:
    try:
        result = exec_in_container(container_name, command)
    except HTTPException:
        return None

    if result.exit_code != 0:
        return None
    return result.output


def tc_server_iface_command() -> list[str]:
    route_iface_script = (
        f"iface=$(ip -o route get {SERVER_IP} | "
        "awk '{for (i = 1; i <= NF; i++) if ($i == \"dev\") {print $(i + 1); exit}}'); "
        'tc qdisc show dev "$iface"'
    )
    return ["bash", "-lc", route_iface_script]


def ensure_gateway(gateway: str) -> str:
    if gateway not in GATEWAYS:
        allowed = ", ".join(sorted(GATEWAYS))
        raise HTTPException(status_code=404, detail=f"Gateway invalido. Use: {allowed}")
    return GATEWAYS[gateway]


def ensure_group(group: str) -> str:
    normalized_group = group.lower()
    if normalized_group not in SENSORS:
        allowed = ", ".join(sorted(SENSORS))
        raise HTTPException(status_code=404, detail=f"Grupo invalido. Use: {allowed}")
    return normalized_group


def ensure_sensor(sensor: str) -> str:
    if sensor not in SENSOR_GROUP:
        allowed = ", ".join(sorted(ALL_SENSORS))
        raise HTTPException(status_code=404, detail=f"Sensor invalido. Use: {allowed}")
    return sensor


TC_TOKEN_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)?(?:[a-z]+)?$")


def ensure_tc_token(name: str, value: str) -> str:
    if not TC_TOKEN_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Valor invalido para {name}: '{value}' (esperado ex.: 256kbit, 400ms).",
        )
    return value


def number_to_str(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def parse_reading_value(value: str) -> float | int | str:
    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def parse_reading_fields(text: str) -> dict[str, float | int | str]:
    fields = {}
    for token in text.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = parse_reading_value(value)
    return fields


def parse_server_logs(tail: int) -> tuple[list[dict[str, Any]], int]:
    container = get_container("server")
    raw_logs = container.logs(tail=tail).decode("utf-8", errors="replace")
    samples = []
    ignored = 0

    for line in raw_logs.splitlines():
        match = SERVER_LOG_PATTERN.search(line)
        if not match:
            ignored += 1
            continue

        try:
            timestamp = datetime.strptime(match.group("timestamp"), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ignored += 1
            continue

        payload_bytes = match.group("bytes")
        delay_ms = match.group("delay_ms")
        reading = parse_reading_fields(line[match.end():].strip())
        samples.append(
            {
                "timestamp": timestamp,
                "group": match.group("group").lower(),
                "sensor": match.group("sensor"),
                "sequence": int(match.group("sequence")),
                "origin": match.group("origin"),
                "bytes": int(payload_bytes) if payload_bytes else len(line.encode("utf-8")),
                "delay_ms": float(delay_ms) if delay_ms else None,
                "reading": reading,
            }
        )

    return samples, ignored


def server_log_lines_by_group(group: str, tail: int) -> list[str]:
    normalized_group = ensure_group(group).upper()
    container = get_container("server")
    raw_logs = container.logs(tail=tail).decode("utf-8", errors="replace")
    marker = f"grupo={normalized_group} "
    return [line for line in raw_logs.splitlines() if marker in line]


def calculate_group_metrics(group: str, samples: list[dict[str, Any]]) -> GroupMetrics:
    ordered = sorted(samples, key=lambda item: item["timestamp"])
    duration = 0.0
    if len(ordered) > 1:
        duration = (ordered[-1]["timestamp"] - ordered[0]["timestamp"]).total_seconds()
    duration_for_rate = max(duration, 1.0)

    total_bytes = sum(item["bytes"] for item in ordered)
    delays = [item["delay_ms"] for item in ordered if item["delay_ms"] is not None]
    jitter_values = [
        abs(current - previous)
        for previous, current in zip(delays, delays[1:])
    ]

    sequences_by_origin: dict[str, set[int]] = defaultdict(set)
    for item in ordered:
        sequences_by_origin[item["origin"]].add(item["sequence"])

    expected = 0
    missing = 0
    for sequences in sequences_by_origin.values():
        if not sequences:
            continue
        origin_expected = max(sequences) - min(sequences) + 1
        expected += origin_expected
        missing += max(origin_expected - len(sequences), 0)

    packet_loss = (missing / expected * 100) if expected else 0.0

    return GroupMetrics(
        group=group,
        messages=len(ordered),
        bytes=total_bytes,
        duration_seconds=round(duration, 3),
        messages_per_second=round(len(ordered) / duration_for_rate, 3),
        throughput_bps=round((total_bytes * 8) / duration_for_rate, 3),
        avg_delay_ms=round(sum(delays) / len(delays), 3) if delays else None,
        jitter_ms=round(sum(jitter_values) / len(jitter_values), 3) if jitter_values else None,
        expected_messages=expected,
        missing_messages=missing,
        packet_loss_percent=round(packet_loss, 3),
    )


def estimate_missing_sensor_messages(samples: list[dict[str, Any]]) -> tuple[int, int]:
    sequences_by_origin: dict[str, list[int]] = defaultdict(list)
    for item in samples:
        sequences_by_origin[item["origin"]].append(item["sequence"])

    expected = 0
    missing = 0
    for sequences in sequences_by_origin.values():
        ordered_sequences = sorted(set(sequences))
        if not ordered_sequences:
            continue
        if len(ordered_sequences) == 1:
            expected += 1
            continue

        gaps = [
            current - previous
            for previous, current in zip(ordered_sequences, ordered_sequences[1:])
            if current > previous
        ]
        step = min(gaps) if gaps else 1
        origin_expected = ((ordered_sequences[-1] - ordered_sequences[0]) // step) + 1
        expected += origin_expected
        missing += max(origin_expected - len(ordered_sequences), 0)

    return expected, missing


def calculate_reading_stats(samples: list[dict[str, Any]]) -> dict[str, ReadingFieldStats]:
    values_by_field: dict[str, list[float | int | str]] = defaultdict(list)
    for item in samples:
        for key, value in item["reading"].items():
            values_by_field[key].append(value)

    stats = {}
    for key, values in sorted(values_by_field.items()):
        numeric_values = [value for value in values if isinstance(value, int | float)]
        if numeric_values:
            stats[key] = ReadingFieldStats(
                samples=len(values),
                min=min(numeric_values),
                max=max(numeric_values),
                avg=round(sum(numeric_values) / len(numeric_values), 3),
                last=values[-1],
            )
        else:
            stats[key] = ReadingFieldStats(
                samples=len(values),
                min=None,
                max=None,
                avg=None,
                last=values[-1],
            )
    return stats


def calculate_sensor_metrics(
    group: str,
    sensor: str,
    samples: list[dict[str, Any]],
) -> SensorMetrics:
    ordered = sorted(samples, key=lambda item: item["timestamp"])
    duration = 0.0
    if len(ordered) > 1:
        duration = (ordered[-1]["timestamp"] - ordered[0]["timestamp"]).total_seconds()
    duration_for_rate = max(duration, 1.0)

    total_bytes = sum(item["bytes"] for item in ordered)
    delays = [item["delay_ms"] for item in ordered if item["delay_ms"] is not None]
    jitter_values = [
        abs(current - previous)
        for previous, current in zip(delays, delays[1:])
    ]
    expected, missing = estimate_missing_sensor_messages(ordered)
    packet_loss = (missing / expected * 100) if expected else 0.0

    return SensorMetrics(
        group=group,
        sensor=sensor,
        origins=sorted({item["origin"] for item in ordered}),
        messages=len(ordered),
        bytes=total_bytes,
        duration_seconds=round(duration, 3),
        messages_per_second=round(len(ordered) / duration_for_rate, 3),
        throughput_bps=round((total_bytes * 8) / duration_for_rate, 3),
        avg_payload_bytes=round(total_bytes / len(ordered), 3) if ordered else 0.0,
        avg_delay_ms=round(sum(delays) / len(delays), 3) if delays else None,
        min_delay_ms=round(min(delays), 3) if delays else None,
        max_delay_ms=round(max(delays), 3) if delays else None,
        jitter_ms=round(sum(jitter_values) / len(jitter_values), 3) if jitter_values else None,
        expected_messages=expected,
        missing_messages=missing,
        packet_loss_percent=round(packet_loss, 3),
        first_seen=ordered[0]["timestamp"].isoformat() if ordered else None,
        last_seen=ordered[-1]["timestamp"].isoformat() if ordered else None,
        last_sequence=ordered[-1]["sequence"] if ordered else None,
        last_reading=ordered[-1]["reading"] if ordered else {},
        reading_stats=calculate_reading_stats(ordered),
    )


def calculate_sensor_metrics_collection(tail: int) -> SensorMetricsCollection:
    samples, ignored = parse_server_logs(tail)
    samples_by_group_sensor: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for sample in samples:
        samples_by_group_sensor[sample["group"]][sample["sensor"]].append(sample)

    groups: dict[str, dict[str, SensorMetrics]] = {group: {} for group in sorted(SENSORS)}
    for group, sensors in sorted(samples_by_group_sensor.items()):
        groups[group] = {
            sensor: calculate_sensor_metrics(group, sensor, sensor_samples)
            for sensor, sensor_samples in sorted(sensors.items())
        }

    return SensorMetricsCollection(
        source=f"server logs tail={tail}",
        parsed_lines=len(samples),
        ignored_lines=ignored,
        groups=groups,
    )


def calculate_traffic_metrics(tail: int) -> TrafficMetrics:
    samples, ignored = parse_server_logs(tail)
    samples_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        samples_by_group[sample["group"]].append(sample)

    return TrafficMetrics(
        source=f"server logs tail={tail}",
        parsed_lines=len(samples),
        ignored_lines=ignored,
        groups={
            group: calculate_group_metrics(group, samples_by_group.get(group, []))
            for group in sorted(SENSORS)
        },
    )


def gateway_status(group: str) -> GatewayStatus:
    normalized_group = ensure_group(group)
    container_name = GATEWAYS[normalized_group]

    try:
        container = get_container(container_name)
        docker_status = container.status
        image = container.image.tags[0] if container.image.tags else container.image.short_id
        container_id = container.short_id
    except HTTPException:
        docker_status = "missing"
        image = None
        container_id = None

    interfaces = exec_output_or_none(container_name, ["ip", "-br", "addr"])
    ip_forward_output = exec_output_or_none(container_name, ["cat", "/proc/sys/net/ipv4/ip_forward"])
    tc_output = exec_output_or_none(container_name, tc_server_iface_command())
    iptables_output = exec_output_or_none(container_name, ["iptables", "-L", "FORWARD", "-v", "-n"])

    return GatewayStatus(
        group=normalized_group,
        container=container_name,
        docker_status=docker_status,
        running=docker_status == "running",
        image=image,
        id=container_id,
        ip_forward=ip_forward_output.strip() if ip_forward_output else None,
        interfaces=interfaces,
        tc_eth1=tc_output,
        policies=GatewayPolicyStatus(
            bandwidth_limit_active=bool(tc_output and " tbf " in tc_output),
            triage_block_active=bool(
                iptables_output
                and "DROP" in iptables_output
                and "10.0.3.0/24" in iptables_output
                and "10.0.100.10" in iptables_output
            ),
            network_emulation_active=bool(tc_output and " netem " in tc_output),
        ),
    )


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    docker_client().ping()
    return {"status": "ok", "docker": "ok"}


@app.get("/containers", tags=["sistema"])
def containers() -> list[dict[str, Any]]:
    return sorted(
        [container_summary(container) for container in compose_containers()],
        key=lambda item: item["name"],
    )


@app.get("/status", tags=["sistema"])
def status() -> dict[str, Any]:
    containers_by_name = {container.name: container for container in compose_containers()}
    expected = ["controller", "dashboard", "server", *GATEWAYS.values()]
    expected.extend(sensor for group in SENSORS.values() for sensor in group)

    services = {}
    for name in expected:
        container = containers_by_name.get(name)
        services[name] = container.status if container else "missing"

    return {
        "project": PROJECT_NAME,
        "total_containers": len(containers_by_name),
        "running": sum(1 for state in services.values() if state == "running"),
        "services": services,
    }


@app.get("/logs/{container_name}", tags=["logs"])
def logs(container_name: str, tail: int = Query(default=80, ge=1, le=500)) -> dict[str, str]:
    container = get_container(container_name)
    output = container.logs(tail=tail).decode("utf-8", errors="replace")
    return {"container": container_name, "logs": output}


@app.get("/metrics/traffic", response_model=TrafficMetrics, tags=["metricas"])
def traffic_metrics(tail: int = Query(default=1000, ge=10, le=5000)) -> TrafficMetrics:
    return calculate_traffic_metrics(tail)


@app.get("/metrics/traffic/{group}", response_model=GroupMetrics, tags=["metricas"])
def traffic_metrics_by_group(
    group: str,
    tail: int = Query(default=1000, ge=10, le=5000),
) -> GroupMetrics:
    normalized_group = ensure_group(group)
    metrics = calculate_traffic_metrics(tail)
    return metrics.groups[normalized_group]


@app.get("/sensors/metrics", response_model=SensorMetricsCollection, tags=["metricas"])
def sensor_metrics(tail: int = Query(default=1000, ge=10, le=5000)) -> SensorMetricsCollection:
    return calculate_sensor_metrics_collection(tail)


@app.get("/groups", response_model=list[GroupInfo], tags=["grupos"])
def groups() -> list[GroupInfo]:
    return [
        GroupInfo(group=group, gateway=GATEWAYS[group], sensors=sensors)
        for group, sensors in SENSORS.items()
    ]


@app.get("/groups/{group}", response_model=GroupInfo, tags=["grupos"])
def group_info(group: str) -> GroupInfo:
    normalized_group = ensure_group(group)
    return GroupInfo(
        group=normalized_group,
        gateway=GATEWAYS[normalized_group],
        sensors=SENSORS[normalized_group],
    )


@app.get("/groups/{group}/sensors", tags=["grupos"])
def group_sensors(group: str) -> dict[str, list[str]]:
    normalized_group = ensure_group(group)
    return {"group": normalized_group, "sensors": SENSORS[normalized_group]}


@app.get("/groups/{group}/sensors/metrics", response_model=dict[str, SensorMetrics], tags=["grupos"])
def group_sensor_metrics(
    group: str,
    tail: int = Query(default=1000, ge=10, le=5000),
) -> dict[str, SensorMetrics]:
    normalized_group = ensure_group(group)
    metrics = calculate_sensor_metrics_collection(tail)
    return metrics.groups[normalized_group]


@app.get(
    "/groups/{group}/sensors/{sensor}/metrics",
    response_model=SensorMetrics,
    tags=["grupos"],
)
def single_sensor_metrics(
    group: str,
    sensor: str,
    tail: int = Query(default=1000, ge=10, le=5000),
) -> SensorMetrics:
    normalized_group = ensure_group(group)
    metrics = calculate_sensor_metrics_collection(tail)
    group_metrics = metrics.groups.get(normalized_group)
    if not group_metrics or sensor not in group_metrics:
        raise HTTPException(status_code=404, detail=f"Sensor sem metricas: {sensor}")
    return group_metrics[sensor]


@app.get("/groups/{group}/gateway", tags=["grupos"])
def group_gateway(group: str) -> dict[str, str]:
    normalized_group = ensure_group(group)
    return {"group": normalized_group, "gateway": GATEWAYS[normalized_group]}


@app.get("/groups/{group}/gateway/iptables", tags=["grupos"])
def group_gateway_iptables(group: str) -> CommandResult:
    normalized_group = ensure_group(group)
    return gateway_iptables(normalized_group)


@app.get("/groups/{group}/gateway/tc", tags=["grupos"])
def group_gateway_tc(group: str) -> CommandResult:
    normalized_group = ensure_group(group)
    return gateway_tc(normalized_group)


@app.get("/groups/{group}/gateway/interfaces", tags=["grupos"])
def group_gateway_interfaces(group: str) -> CommandResult:
    normalized_group = ensure_group(group)
    return gateway_interfaces(normalized_group)


@app.get("/groups/{group}/routes", response_model=GroupRoutes, tags=["grupos"])
def group_routes(group: str) -> GroupRoutes:
    normalized_group = ensure_group(group)
    gateway = exec_in_container(GATEWAYS[normalized_group], ["ip", "route"])
    sensor_routes = {
        sensor: exec_in_container(sensor, ["ip", "route"])
        for sensor in SENSORS[normalized_group]
    }
    return GroupRoutes(group=normalized_group, gateway=gateway, sensors=sensor_routes)


@app.get("/groups/{group}/logs", tags=["grupos"])
def group_logs(group: str, tail: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    normalized_group = ensure_group(group)
    return {
        "group": normalized_group,
        "source": "server",
        "logs": server_log_lines_by_group(normalized_group, tail),
    }


@app.get("/groups/{group}/metrics", response_model=GroupMetrics, tags=["grupos"])
def group_metrics(
    group: str,
    tail: int = Query(default=1000, ge=10, le=5000),
) -> GroupMetrics:
    normalized_group = ensure_group(group)
    return traffic_metrics_by_group(normalized_group, tail)


@app.get("/sensors", tags=["compatibilidade"])
def sensors() -> dict[str, list[str]]:
    return SENSORS


@app.get("/gateways", response_model=dict[str, GatewayStatus], tags=["gateways"])
def gateways() -> dict[str, GatewayStatus]:
    return {group: gateway_status(group) for group in GATEWAYS}


@app.get("/gateways/{gateway}/iptables", tags=["compatibilidade"])
def gateway_iptables(gateway: str) -> CommandResult:
    container_name = ensure_gateway(gateway)
    return exec_in_container(container_name, ["iptables", "-L", "FORWARD", "-v", "-n"])


@app.get("/gateways/{gateway}/tc", tags=["compatibilidade"])
def gateway_tc(gateway: str) -> CommandResult:
    container_name = ensure_gateway(gateway)
    return exec_in_container(container_name, tc_server_iface_command())


@app.get("/gateways/{gateway}/interfaces", tags=["compatibilidade"])
def gateway_interfaces(gateway: str) -> CommandResult:
    container_name = ensure_gateway(gateway)
    return exec_in_container(container_name, ["ip", "-br", "addr"])


@app.get("/routes/{container_name}", tags=["compatibilidade"])
def routes(container_name: str) -> CommandResult:
    return exec_in_container(container_name, ["ip", "route"])


@app.get("/policies", response_model=dict[str, PolicyEndpoint], tags=["politicas"])
def policies() -> dict[str, PolicyEndpoint]:
    return {key: PolicyEndpoint(**value) for key, value in POLICY_ENDPOINTS.items()}


@app.post("/policies/enfermaria/limit", response_model=CommandResult, tags=["politicas"])
def limit_enfermaria() -> CommandResult:
    return exec_in_container(
        "gw-enfermaria",
        ["bash", "-lc", "/opt/vnf/limitar_enfermaria.sh"],
    )


@app.post("/policies/enfermaria/restore", response_model=CommandResult, tags=["politicas"])
def restore_enfermaria() -> CommandResult:
    return exec_in_container(
        "gw-enfermaria",
        ["bash", "-lc", "/opt/vnf/restaurar_politicas.sh"],
    )


@app.post("/policies/triagem/block", response_model=CommandResult, tags=["politicas"])
def block_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/bloquear_triagem.sh"])


@app.post("/policies/triagem/unblock", response_model=CommandResult, tags=["politicas"])
def unblock_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/restaurar_politicas.sh"])


def apply_tbf(group: str, request: TbfRequest) -> CommandResult:
    normalized_group = ensure_group(group)
    rate = ensure_tc_token("rate", request.rate)
    burst = ensure_tc_token("burst", request.burst)
    latency = ensure_tc_token("latency", request.latency)
    env = f"LIMIT_RATE={shlex.quote(rate)} LIMIT_BURST={shlex.quote(burst)} LIMIT_LATENCY={shlex.quote(latency)}"
    return exec_in_container(
        GATEWAYS[normalized_group],
        ["bash", "-lc", f"{env} /opt/vnf/aplicar_tbf.sh"],
    )


def clear_tbf(group: str) -> CommandResult:
    normalized_group = ensure_group(group)
    return exec_in_container(
        GATEWAYS[normalized_group],
        ["bash", "-lc", "/opt/vnf/remover_tbf.sh"],
    )


def apply_netem(group: str, request: NetemRequest) -> CommandResult:
    normalized_group = ensure_group(group)
    has_param = any(
        getattr(request, field) > 0
        for field in (
            "delay_ms",
            "jitter_ms",
            "loss_pct",
            "duplicate_pct",
            "corrupt_pct",
            "reorder_pct",
        )
    )
    if not has_param:
        raise HTTPException(
            status_code=400,
            detail="Informe ao menos um parametro netem maior que zero.",
        )

    env_parts = [
        f"NETEM_DELAY_MS={number_to_str(request.delay_ms)}",
        f"NETEM_JITTER_MS={number_to_str(request.jitter_ms)}",
        f"NETEM_LOSS_PCT={number_to_str(request.loss_pct)}",
        f"NETEM_DUPLICATE_PCT={number_to_str(request.duplicate_pct)}",
        f"NETEM_CORRUPT_PCT={number_to_str(request.corrupt_pct)}",
        f"NETEM_REORDER_PCT={number_to_str(request.reorder_pct)}",
    ]
    env = " ".join(env_parts)
    return exec_in_container(
        GATEWAYS[normalized_group],
        ["bash", "-lc", f"{env} /opt/vnf/aplicar_netem.sh"],
    )


def clear_netem(group: str) -> CommandResult:
    normalized_group = ensure_group(group)
    return exec_in_container(
        GATEWAYS[normalized_group],
        ["bash", "-lc", "/opt/vnf/remover_netem.sh"],
    )


def read_sensor_control(sensor: str) -> dict[str, Any]:
    output = exec_output_or_none(sensor, ["cat", SENSOR_CONTROL_FILE])
    if not output:
        return {}
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_sensor_control(sensor: str, control: dict[str, Any]) -> CommandResult:
    serialized = json.dumps(control)
    script = f"cat > {SENSOR_CONTROL_FILE} <<'JSON'\n{serialized}\nJSON"
    return exec_in_container(sensor, ["bash", "-lc", script])


def merge_sensor_control(sensor: str, update: SensorControl) -> dict[str, Any]:
    current = read_sensor_control(sensor)
    patch = update.model_dump(exclude_unset=True, exclude_none=True)
    current.update(patch)
    write_sensor_control(sensor, current)
    return current


def sensor_container_status(sensor: str) -> str:
    try:
        container = get_container(sensor)
        return container.status
    except HTTPException:
        return "missing"


@app.post("/policies/{group}/limit", response_model=CommandResult, tags=["politicas"])
def limit_group(group: str, request: TbfRequest | None = None) -> CommandResult:
    return apply_tbf(group, request or TbfRequest())


@app.post("/policies/{group}/limit/clear", response_model=CommandResult, tags=["politicas"])
def limit_clear(group: str) -> CommandResult:
    return clear_tbf(group)


@app.post("/policies/{group}/netem", response_model=CommandResult, tags=["politicas"])
def netem_group(group: str, request: NetemRequest) -> CommandResult:
    return apply_netem(group, request)


@app.post("/policies/{group}/netem/clear", response_model=CommandResult, tags=["politicas"])
def netem_clear(group: str) -> CommandResult:
    return clear_netem(group)


@app.get("/sensors/{sensor}/config", response_model=SensorControlState, tags=["sensores"])
def sensor_config(sensor: str) -> SensorControlState:
    ensure_sensor(sensor)
    return SensorControlState(
        sensor=sensor,
        group=SENSOR_GROUP.get(sensor),
        container_status=sensor_container_status(sensor),
        control=read_sensor_control(sensor),
    )


@app.post("/sensors/{sensor}/config", response_model=SensorControlState, tags=["sensores"])
def sensor_config_update(sensor: str, update: SensorControl) -> SensorControlState:
    ensure_sensor(sensor)
    if not update.model_dump(exclude_unset=True, exclude_none=True):
        raise HTTPException(
            status_code=400,
            detail="Informe ao menos um campo: interval, payload_padding_bytes ou enabled.",
        )
    merged = merge_sensor_control(sensor, update)
    return SensorControlState(
        sensor=sensor,
        group=SENSOR_GROUP.get(sensor),
        container_status=sensor_container_status(sensor),
        control=merged,
    )


@app.post("/sensors/{sensor}/start", tags=["sensores"])
def sensor_start(sensor: str) -> dict[str, str]:
    ensure_sensor(sensor)
    container = get_container(sensor)
    container.start()
    container.reload()
    return {"sensor": sensor, "status": container.status}


@app.post("/sensors/{sensor}/stop", tags=["sensores"])
def sensor_stop(sensor: str) -> dict[str, str]:
    ensure_sensor(sensor)
    container = get_container(sensor)
    container.stop(timeout=5)
    container.reload()
    return {"sensor": sensor, "status": container.status}


SCENARIOS: dict[str, dict[str, Any]] = {
    "normal": {
        "description": "Restaura todas as politicas e a configuracao dinamica dos sensores.",
        "actions": [
            {"type": "clear_netem", "group": "uti"},
            {"type": "clear_netem", "group": "enfermaria"},
            {"type": "clear_netem", "group": "triagem"},
            {"type": "restore_all_policies"},
            {"type": "reset_all_sensors"},
        ],
    },
    "congestionamento_enfermaria": {
        "description": "Aplica latencia e perda na enfermaria para simular congestionamento.",
        "actions": [
            {
                "type": "netem",
                "group": "enfermaria",
                "params": {"delay_ms": 200, "jitter_ms": 50, "loss_pct": 5},
            },
        ],
    },
    "surto_uti": {
        "description": "Acelera o envio dos sensores da UTI e infla o payload para gerar rajada.",
        "actions": [
            {
                "type": "sensor_config",
                "sensor": "sensor-uti-1",
                "params": {"interval": 0.2, "payload_padding_bytes": 2048},
            },
            {
                "type": "sensor_config",
                "sensor": "sensor-uti-2",
                "params": {"interval": 0.2, "payload_padding_bytes": 2048},
            },
            {
                "type": "sensor_config",
                "sensor": "sensor-uti-3",
                "params": {"interval": 0.2, "payload_padding_bytes": 2048},
            },
        ],
    },
    "falha_triagem": {
        "description": "Degrada severamente a triagem (delay 500ms, jitter 100ms, perda 30%).",
        "actions": [
            {
                "type": "netem",
                "group": "triagem",
                "params": {"delay_ms": 500, "jitter_ms": 100, "loss_pct": 30},
            },
        ],
    },
}


def reset_all_sensors() -> list[dict[str, Any]]:
    results = []
    default_control = {"interval": 2.0, "payload_padding_bytes": 0, "enabled": True}
    for sensor in ALL_SENSORS:
        try:
            write_sensor_control(sensor, default_control)
            results.append({"sensor": sensor, "control": default_control, "ok": True})
        except HTTPException as exc:
            results.append({"sensor": sensor, "ok": False, "error": exc.detail})
    return results


def restore_all_policies_results() -> dict[str, CommandResult]:
    return {
        "enfermaria": restore_enfermaria(),
        "triagem": unblock_triagem(),
    }


def execute_scenario_action(action: dict[str, Any]) -> dict[str, Any]:
    action_type = action.get("type")

    if action_type == "netem":
        group = action["group"]
        params = action.get("params", {})
        result = apply_netem(group, NetemRequest(**params))
        return {"type": action_type, "group": group, "params": params, "result": result.model_dump()}

    if action_type == "clear_netem":
        group = action["group"]
        result = clear_netem(group)
        return {"type": action_type, "group": group, "result": result.model_dump()}

    if action_type == "tbf":
        group = action["group"]
        params = action.get("params", {})
        result = apply_tbf(group, TbfRequest(**params))
        return {"type": action_type, "group": group, "params": params, "result": result.model_dump()}

    if action_type == "sensor_config":
        sensor = ensure_sensor(action["sensor"])
        params = action.get("params", {})
        merged = merge_sensor_control(sensor, SensorControl(**params))
        return {"type": action_type, "sensor": sensor, "params": params, "control": merged}

    if action_type == "restore_all_policies":
        result = restore_all_policies_results()
        return {"type": action_type, "result": {k: v.model_dump() for k, v in result.items()}}

    if action_type == "reset_all_sensors":
        return {"type": action_type, "results": reset_all_sensors()}

    raise HTTPException(status_code=500, detail=f"Tipo de acao desconhecido: {action_type}")


@app.get("/scenarios", tags=["cenarios"])
def list_scenarios() -> dict[str, dict[str, Any]]:
    return {
        name: {"description": data["description"], "actions": data["actions"]}
        for name, data in SCENARIOS.items()
    }


@app.post("/scenarios/{name}", tags=["cenarios"])
def apply_scenario(name: str) -> dict[str, Any]:
    if name not in SCENARIOS:
        allowed = ", ".join(sorted(SCENARIOS))
        raise HTTPException(status_code=404, detail=f"Cenario invalido. Use: {allowed}")

    scenario = SCENARIOS[name]
    executed = [execute_scenario_action(action) for action in scenario["actions"]]
    return {
        "scenario": name,
        "description": scenario["description"],
        "actions_executed": executed,
    }


@app.post("/policies/restore", response_model=dict[str, CommandResult], tags=["politicas"])
def restore_all() -> dict[str, CommandResult]:
    return restore_all_policies_results()


def fetch_latest_snapshots(group: str | None, sensor: str | None) -> list[SensorMetricsSnapshot]:
    if group is not None:
        ensure_group(group)
    if sensor is not None:
        ensure_sensor(sensor)
    try:
        rows = storage.latest_snapshots(METRICS_DB_PATH, group=group, sensor=sensor)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Falha ao consultar storage: {exc}") from exc
    return [SensorMetricsSnapshot(**row) for row in rows]


@app.get(
    "/timeseries/sensors/latest",
    response_model=list[SensorMetricsSnapshot],
    tags=["timeseries"],
)
def timeseries_latest(
    group: str | None = Query(default=None, description="Filtrar por grupo (uti, enfermaria, triagem)."),
    sensor: str | None = Query(default=None, description="Filtrar por nome do sensor (ex.: sensor-cardiaco)."),
) -> list[SensorMetricsSnapshot]:
    return fetch_latest_snapshots(group, sensor)


@app.get("/timeseries/stats", response_model=TimeseriesStats, tags=["timeseries"])
def timeseries_stats() -> TimeseriesStats:
    try:
        data = storage.stats(METRICS_DB_PATH)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Falha ao consultar storage: {exc}") from exc
    return TimeseriesStats(
        db_path=METRICS_DB_PATH,
        ingest_enabled=INGEST_ENABLED,
        ingest_interval_s=INGEST_INTERVAL_S,
        ingest_tail=INGEST_TAIL,
        total_rows=data.get("total_rows", 0) or 0,
        first_capture=data.get("first_capture"),
        last_capture=data.get("last_capture"),
        distinct_groups=data.get("distinct_groups", 0) or 0,
        distinct_sensors=data.get("distinct_sensors", 0) or 0,
    )


@app.get("/timeseries/metrics", tags=["timeseries"])
def timeseries_metrics() -> dict[str, list[str]]:
    return {"metrics": list(storage.ALLOWED_METRICS)}


@app.get(
    "/timeseries/sensors",
    response_model=PaginatedSnapshots,
    tags=["timeseries"],
)
def timeseries_sensors(
    group: str | None = Query(default=None, description="Filtrar por grupo."),
    sensor: str | None = Query(default=None, description="Filtrar por sensor."),
    since: str | None = Query(default=None, description="Data/hora minima (ISO 8601)."),
    until: str | None = Query(default=None, description="Data/hora maxima (ISO 8601)."),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> PaginatedSnapshots:
    if group is not None:
        ensure_group(group)
    if sensor is not None:
        ensure_sensor(sensor)
    try:
        total = storage.count_snapshots(
            METRICS_DB_PATH, group=group, sensor=sensor, since=since, until=until
        )
        rows = storage.query_snapshots(
            METRICS_DB_PATH,
            group=group,
            sensor=sensor,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
            order=order,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Falha ao consultar storage: {exc}") from exc

    return PaginatedSnapshots(
        total=total,
        limit=limit,
        offset=offset,
        order=order,
        items=[SensorMetricsSnapshot(**row) for row in rows],
    )


@app.get(
    "/timeseries/series",
    response_model=TimeseriesSeries,
    tags=["timeseries"],
)
def timeseries_series(
    metric: str = Query(..., description="Nome da metrica. Use /timeseries/metrics para listar."),
    group: str | None = Query(default=None, description="Filtrar por grupo."),
    sensor: str | None = Query(default=None, description="Filtrar por sensor."),
    since: str | None = Query(default=None, description="Data/hora minima (ISO 8601)."),
    until: str | None = Query(default=None, description="Data/hora maxima (ISO 8601)."),
    limit: int = Query(default=5000, ge=1, le=20000),
) -> TimeseriesSeries:
    if group is not None:
        ensure_group(group)
    if sensor is not None:
        ensure_sensor(sensor)
    try:
        rows = storage.query_series(
            METRICS_DB_PATH,
            metric=metric,
            group=group,
            sensor=sensor,
            since=since,
            until=until,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Falha ao consultar storage: {exc}") from exc

    grouped: dict[tuple[str, str], list[SeriesPoint]] = defaultdict(list)
    for row in rows:
        key = (row["grupo"], row["sensor"])
        grouped[key].append(SeriesPoint(t=row["captured_at"], v=row["value"]))

    series = [
        SensorSeries(group=grupo, sensor=sensor_name, points=points)
        for (grupo, sensor_name), points in sorted(grouped.items())
    ]
    return TimeseriesSeries(metric=metric, since=since, until=until, series=series)
