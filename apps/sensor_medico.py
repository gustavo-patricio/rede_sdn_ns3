#!/usr/bin/env python3
"""Sensor medico simulado para UTI, enfermaria e triagem."""

from __future__ import annotations

import argparse
import json
import random
import socket
import time
from datetime import datetime, timezone


SENSORS = {
    "uti": [
        ("sensor-cardiaco", {"batimento_bpm": (70, 98)}),
        ("sensor-oxigenacao", {"oxigenacao_pct": (94, 100)}),
        ("sensor-pressao", {"sistolica": (110, 135), "diastolica": (70, 88)}),
    ],
    "enfermaria": [
        ("sensor-temperatura", {"temperatura_c": (36.1, 37.4)}),
        ("sensor-glicemia", {"glicemia_mg_dl": (82, 128)}),
        ("sensor-pressao", {"sistolica": (108, 132), "diastolica": (68, 86)}),
    ],
    "triagem": [
        ("sensor-triagem", {"prioridade": ("normal", "observacao", "urgente")}),
        ("oximetro-portatil", {"oxigenacao_pct": (93, 100)}),
        ("monitor-portatil", {"batimento_bpm": (72, 110), "temperatura_c": (36.0, 38.2)}),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sensor medico simulado")
    parser.add_argument("--grupo", choices=sorted(SENSORS), required=True)
    parser.add_argument("--host", default="127.0.0.1", help="Endereco do servidor")
    parser.add_argument("--port", type=int, default=9000, help="Porta UDP do servidor")
    parser.add_argument("--interval", type=float, default=1.0, help="Intervalo entre envios")
    parser.add_argument("--count", type=int, default=0, help="Quantidade de mensagens; 0 = infinito")
    return parser.parse_args()


def random_value(bounds: tuple) -> int | float | str:
    first, second, *rest = bounds
    if rest:
        choices = (first, second, *rest)
        return random.choice(choices)
    if isinstance(first, float) or isinstance(second, float):
        return round(random.uniform(first, second), 1)
    return random.randint(first, second)


def build_reading(group: str, sequence: int) -> dict:
    sensor, fields = SENSORS[group][sequence % len(SENSORS[group])]
    return {
        "grupo": group,
        "sensor": sensor,
        "sequencia": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "leitura": {field: random_value(bounds) for field, bounds in fields.items()},
    }


def main() -> None:
    args = parse_args()
    target = (args.host, args.port)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        sequence = 1
        while args.count == 0 or sequence <= args.count:
            payload = build_reading(args.grupo, sequence)
            data = json.dumps(payload).encode("utf-8")
            client.sendto(data, target)
            print(
                f"[SENSOR] grupo={args.grupo} sensor={payload['sensor']} "
                f"seq={sequence} destino={args.host}:{args.port}",
                flush=True,
            )
            sequence += 1
            if args.count == 0 or sequence <= args.count:
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
