#!/usr/bin/env python3
"""API REST para operar e diagnosticar o ambiente SDN/NFV local."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import docker
from docker.errors import DockerException, NotFound
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


PROJECT_NAME = os.getenv("COMPOSE_PROJECT_NAME", "atividad_6")

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


app = FastAPI(
    title="API SDN/NFV - Rede Hospitalar IoMT",
    description="API local para diagnosticar containers e aplicar politicas VNF.",
    version="0.1.0",
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

    groups = {}
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
            group: calculate_group_metrics(group, group_samples)
            for group, group_samples in sorted(samples_by_group.items())
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
    tc_output = exec_output_or_none(container_name, ["tc", "qdisc", "show", "dev", "eth1"])
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
    metrics = calculate_traffic_metrics(tail)
    normalized_group = group.lower()
    if normalized_group not in metrics.groups:
        raise HTTPException(status_code=404, detail=f"Grupo sem metricas: {group}")
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
    if normalized_group not in metrics.groups:
        raise HTTPException(status_code=404, detail=f"Grupo sem metricas: {group}")
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
    if not group_metrics:
        raise HTTPException(status_code=404, detail=f"Grupo sem metricas: {group}")
    if sensor not in group_metrics:
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
    return exec_in_container(container_name, ["tc", "qdisc", "show", "dev", "eth1"])


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
        ["bash", "-lc", "WAN_IFACE=eth1 /opt/vnf/limitar_enfermaria.sh"],
    )


@app.post("/policies/enfermaria/restore", response_model=CommandResult, tags=["politicas"])
def restore_enfermaria() -> CommandResult:
    return exec_in_container(
        "gw-enfermaria",
        ["bash", "-lc", "WAN_IFACE=eth1 /opt/vnf/restaurar_politicas.sh"],
    )


@app.post("/policies/triagem/block", response_model=CommandResult, tags=["politicas"])
def block_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/bloquear_triagem.sh"])


@app.post("/policies/triagem/unblock", response_model=CommandResult, tags=["politicas"])
def unblock_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/restaurar_politicas.sh"])


@app.post("/policies/restore", response_model=dict[str, CommandResult], tags=["politicas"])
def restore_all() -> dict[str, CommandResult]:
    return {
        "enfermaria": restore_enfermaria(),
        "triagem": unblock_triagem(),
    }
