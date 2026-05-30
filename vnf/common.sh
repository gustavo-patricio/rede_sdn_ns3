#!/usr/bin/env bash

set -euo pipefail

SERVER_IP="${SERVER_IP:-10.0.100.10}"
SERVER_PORT="${SERVER_PORT:-9000}"
UTI_NET="${UTI_NET:-10.0.1.0/24}"
ENFERMARIA_NET="${ENFERMARIA_NET:-10.0.2.0/24}"
TRIAGEM_NET="${TRIAGEM_NET:-10.0.3.0/24}"
WAN_IFACE="${WAN_IFACE:-}"
LIMIT_RATE="${LIMIT_RATE:-256kbit}"
LIMIT_BURST="${LIMIT_BURST:-32kbit}"
LIMIT_LATENCY="${LIMIT_LATENCY:-400ms}"

NETEM_DELAY_MS="${NETEM_DELAY_MS:-0}"
NETEM_JITTER_MS="${NETEM_JITTER_MS:-0}"
NETEM_LOSS_PCT="${NETEM_LOSS_PCT:-0}"
NETEM_DUPLICATE_PCT="${NETEM_DUPLICATE_PCT:-0}"
NETEM_CORRUPT_PCT="${NETEM_CORRUPT_PCT:-0}"
NETEM_REORDER_PCT="${NETEM_REORDER_PCT:-0}"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Erro: comando '$1' nao encontrado." >&2
        exit 1
    fi
}

enable_forwarding() {
    if [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo 0)" = "1" ]; then
        return
    fi

    if [ -w /proc/sys/net/ipv4/ip_forward ] && echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null; then
        return
    fi

    if sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1; then
        return
    fi

    echo "Aviso: nao foi possivel ativar net.ipv4.ip_forward no runtime." >&2
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

iface_for_network() {
    local source_net="$1"

    ip -o route show "$source_net" | awk '
        {
            for (i = 1; i <= NF; i++) {
                if ($i == "dev") {
                    print $(i + 1)
                    exit
                }
            }
        }
    '
}

iface_for_server() {
    if [ -n "$WAN_IFACE" ]; then
        echo "$WAN_IFACE"
        return
    fi

    ip -o route get "$SERVER_IP" | awk '
        {
            for (i = 1; i <= NF; i++) {
                if ($i == "dev") {
                    print $(i + 1)
                    exit
                }
            }
        }
    '
}

ipv4_for_iface() {
    local iface="$1"

    ip -o -4 addr show dev "$iface" | awk '
        {
            split($4, address, "/")
            print address[1]
            exit
        }
    '
}

ensure_udp_forward_to_server() {
    local source_net="$1"
    local lan_iface
    local gateway_ip
    local wan_iface

    lan_iface="$(iface_for_network "$source_net")"
    wan_iface="$(iface_for_server)"

    if [ -z "$lan_iface" ] || [ -z "$wan_iface" ]; then
        echo "Erro: nao foi possivel detectar interfaces para $source_net -> $SERVER_IP." >&2
        exit 1
    fi

    gateway_ip="$(ipv4_for_iface "$lan_iface")"
    if [ -z "$gateway_ip" ]; then
        echo "Erro: nao foi possivel detectar IP do gateway em $lan_iface." >&2
        exit 1
    fi

    iptables -t nat -C PREROUTING \
        -i "$lan_iface" \
        -p udp \
        -d "$gateway_ip" \
        --dport "$SERVER_PORT" \
        -j DNAT \
        --to-destination "$SERVER_IP:$SERVER_PORT" 2>/dev/null || \
        iptables -t nat -A PREROUTING \
            -i "$lan_iface" \
            -p udp \
            -d "$gateway_ip" \
            --dport "$SERVER_PORT" \
            -j DNAT \
            --to-destination "$SERVER_IP:$SERVER_PORT"

    iptables -t nat -C POSTROUTING \
        -o "$wan_iface" \
        -p udp \
        -d "$SERVER_IP" \
        --dport "$SERVER_PORT" \
        -j MASQUERADE 2>/dev/null || \
        iptables -t nat -A POSTROUTING \
            -o "$wan_iface" \
            -p udp \
            -d "$SERVER_IP" \
            --dport "$SERVER_PORT" \
            -j MASQUERADE

    echo "Encaminhamento UDP configurado: $gateway_ip:$SERVER_PORT -> $SERVER_IP:$SERVER_PORT via $wan_iface"
}

remove_triagem_block() {
    while iptables -D FORWARD -s "$TRIAGEM_NET" -d "$SERVER_IP" -j DROP 2>/dev/null; do
        :
    done
}

remove_enfermaria_limit() {
    local iface="${1:-$(iface_for_server)}"

    if [ -n "$iface" ]; then
        tc qdisc del dev "$iface" root 2>/dev/null || true
    fi
}

remove_qdisc_root() {
    local iface="${1:-$(iface_for_server)}"

    if [ -n "$iface" ]; then
        tc qdisc del dev "$iface" root 2>/dev/null || true
    fi
}

is_nonzero_number() {
    local value="$1"

    [ -n "$value" ] && [ "$value" != "0" ] && [ "$value" != "0.0" ]
}

build_netem_args() {
    local args=()

    if is_nonzero_number "$NETEM_DELAY_MS"; then
        if is_nonzero_number "$NETEM_JITTER_MS"; then
            args+=(delay "${NETEM_DELAY_MS}ms" "${NETEM_JITTER_MS}ms" distribution normal)
        else
            args+=(delay "${NETEM_DELAY_MS}ms")
        fi
    fi

    if is_nonzero_number "$NETEM_LOSS_PCT"; then
        args+=(loss "${NETEM_LOSS_PCT}%")
    fi

    if is_nonzero_number "$NETEM_DUPLICATE_PCT"; then
        args+=(duplicate "${NETEM_DUPLICATE_PCT}%")
    fi

    if is_nonzero_number "$NETEM_CORRUPT_PCT"; then
        args+=(corrupt "${NETEM_CORRUPT_PCT}%")
    fi

    if is_nonzero_number "$NETEM_REORDER_PCT"; then
        args+=(reorder "${NETEM_REORDER_PCT}%")
    fi

    echo "${args[@]}"
}
