#!/usr/bin/env bash
# The factory's one test command, used by the gates and allowed to the implement stage.
#
#   bash factory/check.sh <agent-name>
#
# Runs the new agent's suite offline: provider keys are removed from the
# environment and <AGENT>_OFFLINE=1 is set, so no test can reach a real model.
# FACTORY_TEST_CMD replaces the command (for testing the factory itself);
# FACTORY_PYTHON picks the interpreter (default python3).

set -uo pipefail
AGENT=${1:?usage: bash factory/check.sh <agent-name>}
cd "$(git rev-parse --show-toplevel)" || exit 2
if [ -n "${FACTORY_TEST_CMD:-}" ]; then exec bash -c "$FACTORY_TEST_CMD"; fi

ENVP=$(printf '%s' "$AGENT" | tr 'a-z-' 'A-Z_')
export PYTHONDONTWRITEBYTECODE=1
exec env -u GEMINI_API_KEY -u GOOGLE_API_KEY -u GOOGLE_AI_STUDIO_KEY -u ANTHROPIC_API_KEY -u OPENAI_API_KEY \
  "${ENVP}_OFFLINE=1" "${ENVP}_DATA_DIR=$(mktemp -d)" \
  "${FACTORY_PYTHON:-python3}" -m pytest -q -p no:cacheprovider "agents/$AGENT"
