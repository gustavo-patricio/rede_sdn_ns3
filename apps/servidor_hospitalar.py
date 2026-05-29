#!/usr/bin/env python3
"""Servidor UDP simples para receber leituras dos sensores medicos."""

from __future__ import annotations

import argparse
import json
import socket
from datetime import datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servidor hospitalar central")
    parser.add_argument("--host", default="0.0.0.0", help="Endereco de escuta")
    parser.add_argument("--port", type=int, default=9000, help="Porta UDP de escuta")
    return parser.parse_args()


def format_reading(payload: dict, address: tuple[str, int]) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    group = str(payload.get("grupo", "desconhecido")).upper()
    sensor = payload.get("sensor", "sensor-desconhecido")
    reading = payload.get("leitura", {})
    sequence = payload.get("sequencia", "-")

    values = " ".join(f"{key}={value}" for key, value in reading.items())
    return (
        f"[{timestamp}] [HOSPITAL] grupo={group} sensor={sensor} "
        f"seq={sequence} origem={address[0]}:{address[1]} {values}"
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
                print(format_reading(payload, address), flush=True)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                print(
                    f"[HOSPITAL] mensagem invalida de {address[0]}:{address[1]}: {exc}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
