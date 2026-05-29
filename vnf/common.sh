#!/usr/bin/env bash

set -euo pipefail

SERVER_IP="${SERVER_IP:-10.0.100.10}"
UTI_NET="${UTI_NET:-10.0.1.0/24}"
ENFERMARIA_NET="${ENFERMARIA_NET:-10.0.2.0/24}"
TRIAGEM_NET="${TRIAGEM_NET:-10.0.3.0/24}"
WAN_IFACE="${WAN_IFACE:-eth1}"
LIMIT_RATE="${LIMIT_RATE:-256kbit}"
LIMIT_BURST="${LIMIT_BURST:-32kbit}"
LIMIT_LATENCY="${LIMIT_LATENCY:-400ms}"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Erro: comando '$1' nao encontrado." >&2
        exit 1
    fi
}

enable_forwarding() {
    if [ -w /proc/sys/net/ipv4/ip_forward ]; then
        echo 1 > /proc/sys/net/ipv4/ip_forward
    else
        sysctl -w net.ipv4.ip_forward=1 >/dev/null
    fi
}

ensure_forward_accept() {
    local source_net="$1"

    iptables -C FORWARD -s "$source_net" -d "$SERVER_IP" -j ACCEPT 2>/dev/null || \
        iptables -A FORWARD -s "$source_net" -d "$SERVER_IP" -j ACCEPT
    iptables -C FORWARD -d "$source_net" -s "$SERVER_IP" -j ACCEPT 2>/dev/null || \
        iptables -A FORWARD -d "$source_net" -s "$SERVER_IP" -j ACCEPT
}

ensure_log_rule() {
    local source_net="$1"
    local prefix="$2"

    iptables -C FORWARD -s "$source_net" -d "$SERVER_IP" -j LOG --log-prefix "$prefix" 2>/dev/null || \
        iptables -I FORWARD -s "$source_net" -d "$SERVER_IP" -j LOG --log-prefix "$prefix"
}

remove_triagem_block() {
    while iptables -D FORWARD -s "$TRIAGEM_NET" -d "$SERVER_IP" -j DROP 2>/dev/null; do
        :
    done
}

remove_enfermaria_limit() {
    tc qdisc del dev "$WAN_IFACE" root 2>/dev/null || true
}
