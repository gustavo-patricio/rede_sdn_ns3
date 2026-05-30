#!/usr/bin/env python3
"""API REST para operar e diagnosticar o ambiente SDN/NFV local."""

from __future__ import annotations

import os
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


class CommandResult(BaseModel):
    container: str
    command: list[str]
    exit_code: int
    output: str


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


@app.get("/health")
def health() -> dict[str, str]:
    docker_client().ping()
    return {"status": "ok", "docker": "ok"}


@app.get("/containers")
def containers() -> list[dict[str, Any]]:
    return sorted(
        [container_summary(container) for container in compose_containers()],
        key=lambda item: item["name"],
    )


@app.get("/status")
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


@app.get("/logs/{container_name}")
def logs(container_name: str, tail: int = Query(default=80, ge=1, le=500)) -> dict[str, str]:
    container = get_container(container_name)
    output = container.logs(tail=tail).decode("utf-8", errors="replace")
    return {"container": container_name, "logs": output}


@app.get("/sensors")
def sensors() -> dict[str, list[str]]:
    return SENSORS


@app.get("/gateways")
def gateways() -> dict[str, str]:
    return GATEWAYS


@app.get("/gateways/{gateway}/iptables")
def gateway_iptables(gateway: str) -> CommandResult:
    container_name = ensure_gateway(gateway)
    return exec_in_container(container_name, ["iptables", "-L", "FORWARD", "-v", "-n"])


@app.get("/gateways/{gateway}/tc")
def gateway_tc(gateway: str) -> CommandResult:
    container_name = ensure_gateway(gateway)
    return exec_in_container(container_name, ["tc", "qdisc", "show", "dev", "eth1"])


@app.get("/gateways/{gateway}/interfaces")
def gateway_interfaces(gateway: str) -> CommandResult:
    container_name = ensure_gateway(gateway)
    return exec_in_container(container_name, ["ip", "-br", "addr"])


@app.get("/routes/{container_name}")
def routes(container_name: str) -> CommandResult:
    return exec_in_container(container_name, ["ip", "route"])


@app.post("/policies/enfermaria/limit")
def limit_enfermaria() -> CommandResult:
    return exec_in_container(
        "gw-enfermaria",
        ["bash", "-lc", "WAN_IFACE=eth1 /opt/vnf/limitar_enfermaria.sh"],
    )


@app.post("/policies/enfermaria/restore")
def restore_enfermaria() -> CommandResult:
    return exec_in_container(
        "gw-enfermaria",
        ["bash", "-lc", "WAN_IFACE=eth1 /opt/vnf/restaurar_politicas.sh"],
    )


@app.post("/policies/triagem/block")
def block_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/bloquear_triagem.sh"])


@app.post("/policies/triagem/unblock")
def unblock_triagem() -> CommandResult:
    return exec_in_container("gw-triagem", ["bash", "-lc", "/opt/vnf/restaurar_politicas.sh"])


@app.post("/policies/restore")
def restore_all() -> dict[str, CommandResult]:
    return {
        "enfermaria": restore_enfermaria(),
        "triagem": unblock_triagem(),
    }
