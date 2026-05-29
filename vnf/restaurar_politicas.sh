#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command iptables
require_command tc

remove_triagem_block
remove_enfermaria_limit

echo "Politicas restauradas: bloqueio da triagem removido e limitacao da enfermaria removida."
