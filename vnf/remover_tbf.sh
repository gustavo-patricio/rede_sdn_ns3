#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command tc

WAN_IFACE="$(iface_for_server)"
remove_qdisc_root "$WAN_IFACE"

echo "TBF removido de $WAN_IFACE"
