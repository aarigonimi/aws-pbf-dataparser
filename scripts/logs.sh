#!/usr/bin/env bash
set -euo pipefail

# Follow the Batch CloudWatch log group.
#
#   make logs                # follow everything, last hour of history
#   SINCE=15m make logs      # start from a different window
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/env.sh
source "${PROJECT_ROOT}/scripts/env.sh"

SINCE="${SINCE:-1h}"

echo "Following ${CLOUDWATCH_LOG_GROUP_NAME} (Ctrl-C to stop)."
exec aws logs tail "$CLOUDWATCH_LOG_GROUP_NAME" --follow --since "$SINCE" --region "$AWS_REGION"
