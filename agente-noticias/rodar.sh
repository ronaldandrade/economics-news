#!/usr/bin/env bash
# Roda o agente uma vez, à mão. Uso:
#   ./rodar.sh           coleta, resume e abre o PR no GitHub
#   ./rodar.sh --seco    só grava os JSON em saida/seco, sem publicar
set -euo pipefail
cd "$(dirname "$0")"

ENV="$HOME/.config/agente-noticias/env"
[[ -f "$ENV" ]] || { echo "falta $ENV com ANTHROPIC_API_KEY=... (veja o README)"; exit 1; }
[[ -x .venv/bin/python ]] || { echo "falta o ambiente: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
[[ -f config.json ]] || { echo "falta config.json: cp config.exemplo.json config.json"; exit 1; }

set -a; . "$ENV"; set +a
exec .venv/bin/python -m agente_noticias executar "$@"
