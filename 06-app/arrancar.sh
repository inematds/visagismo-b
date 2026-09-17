#!/usr/bin/env bash
# Arranca la demo del analisis de visagismo.
# La primera vez crea el entorno (tarda unos minutos: mediapipe pesa).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "Primera ejecucion: creando el entorno..."
  python3 -m venv venv
  ./venv/bin/pip install -q --upgrade pip
  # Dos pasos a proposito: ver la cabecera de requisitos.txt
  ./venv/bin/pip install -q --no-deps mediapipe==0.10.21
  ./venv/bin/pip install -q -r requisitos.txt
  echo "Entorno listo."
fi

PUERTO="${1:-8000}"
echo
echo "  Demo en marcha:  http://localhost:${PUERTO}"
echo "  Para pararla:    Ctrl+C"
echo
exec ./venv/bin/uvicorn servidor:app --host 127.0.0.1 --port "${PUERTO}"
