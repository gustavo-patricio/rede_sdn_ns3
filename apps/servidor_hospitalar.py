#!/usr/bin/env python3
"""Servidor UDP simples para receber leituras dos sensores medicos."""

from __future__ import annotations

import argparse
import json
import socket
from datetime import datetime, timezone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servidor hospitalar central")
    parser.add_argument("--host", default="0.0.0.0", help="Endereco de escuta")
    parser.add_argument("--port", type=int, default=9000, help="Porta UDP de escuta")
    return parser.parse_args()


def calculate_delay_ms(payload: dict) -> float | None:
    sent_at = payload.get("timestamp")
    if not sent_at:
        return None

    try:
        sent_timestamp = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00"))
    except ValueError:
        return None

    if sent_timestamp.tzinfo is None:
        sent_timestamp = sent_timestamp.replace(tzinfo=timezone.utc)

    delay = datetime.now(timezone.utc) - sent_timestamp
    return round(max(delay.total_seconds() * 1000, 0), 3)


def format_reading(payload: dict, address: tuple[str, int], payload_bytes: int) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    group = str(payload.get("grupo", "desconhecido")).upper()
    sensor = payload.get("sensor", "sensor-desconhecido")
    reading = payload.get("leitura", {})
    sequence = payload.get("sequencia", "-")
    delay_ms = calculate_delay_ms(payload)

    values = " ".join(f"{key}={value}" for key, value in reading.items())
    metrics = f"bytes={payload_bytes}"
    if delay_ms is not None:
        metrics = f"{metrics} delay_ms={delay_ms}"

    return (
        f"[{timestamp}] [HOSPITAL] grupo={group} sensor={sensor} "
        f"seq={sequence} origem={address[0]}:{address[1]} {metrics} {values}"
    )


def main() -> None:
    args = parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((args.host, args.port))
        print(f"[HOSPITAL] servidor UDP ativo em {args.host}:{args.port}", flush=True)

        while True:
            data, address = server.recvfrom(4096)
            try:
                payload = json.loads(data.decode("utf-8"))
                print(format_reading(payload, address, len(data)), flush=True)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                print(
                    f"[HOSPITAL] mensagem invalida de {address[0]}:{address[1]}: {exc}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
