#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command iptables

enable_forwarding
ensure_log_rule "$UTI_NET" "GW_UTI_TRAFEGO: "
ensure_forward_accept "$UTI_NET"

echo "Gateway UTI configurado: $UTI_NET -> $SERVER_IP"
