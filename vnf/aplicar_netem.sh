#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command tc

WAN_IFACE="$(iface_for_server)"
NETEM_ARGS="$(build_netem_args)"

if [ -z "$NETEM_ARGS" ]; then
    echo "Erro: nenhum parametro netem fornecido. Use NETEM_DELAY_MS, NETEM_JITTER_MS, NETEM_LOSS_PCT, NETEM_DUPLICATE_PCT, NETEM_CORRUPT_PCT ou NETEM_REORDER_PCT." >&2
    exit 1
fi

remove_qdisc_root "$WAN_IFACE"
# shellcheck disable=SC2086
tc qdisc add dev "$WAN_IFACE" root netem $NETEM_ARGS

echo "Netem aplicado em $WAN_IFACE: $NETEM_ARGS"
