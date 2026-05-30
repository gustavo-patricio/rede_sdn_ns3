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
        samples.append(
            {
                "timestamp": timestamp,
                "group": match.group("group").lower(),
                "sensor": match.group("sensor"),
                "sequence": int(match.group("sequence")),
                "origin": match.group("origin"),
                "bytes": int(payload_bytes) if payload_bytes else len(line.encode("utf-8")),
                "delay_ms": float(delay_ms) if delay_ms else None,
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


@app.get("/gateways", tags=["compatibilidade"])
def gateways() -> dict[str, str]:
    return GATEWAYS


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


@app.post("/policies/enfermaria/limit", tags=["politicas"])
def limit_enfermaria() -> CommandResult:
    return exec_in_container(
        "gw-enfermaria",
        ["bash", "-lc", "WAN_IFACE=eth1 /opt/vnf/limitar_enfermaria.sh"],
    )


@app.post("/policies/enfermaria/restore", tags=["politicas"])
def restore_enfermaria() -> CommandResult:
    return exec_in_container(
        "gw-enfermaria",
        ["bash", "-lc", "WAN_IFACE=eth1 /opt/vnf/restaurar_politicas.sh"],
    )


@app.post("/policies/triagem/block", tags=["politicas"])
def block_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/bloquear_triagem.sh"])


@app.post("/policies/triagem/unblock", tags=["politicas"])
def unblock_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/restaurar_politicas.sh"])


@app.post("/policies/restore", tags=["politicas"])
def restore_all() -> dict[str, CommandResult]:
    return {
        "enfermaria": restore_enfermaria(),
        "triagem": unblock_triagem(),
    }
