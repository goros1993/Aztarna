#!/bin/bash
# Rehace las capturas del manual (docs/manual/*.png) recorriendo la interfaz real en Chromium.
#
# Uso: docs/capturas/capturar.sh [fase…]     (sin fases, todas)
# Fases: edicion requisitos ejecucion validacion grande resultados excel proyecto
#
# Necesita el .venv del proyecto y Node con Playwright (npm install -g playwright
# o PLAYWRIGHT=/ruta/al/módulo). Cada fase copia los ejemplos a DESTINO (por defecto
# /home/ana/validacion, la ruta que se ve en las capturas) y arranca un servidor limpio.
# Las páginas del informe (16 y 17) son del Word generado y no se rehacen aquí.
set -u
DIR=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$DIR/../.." && pwd)
export DESTINO=${DESTINO:-/home/ana/validacion}
export PLAYWRIGHT=${PLAYWRIGHT:-$(npm root -g)/playwright}
SALIDA=${SALIDA:-$REPO/docs/manual}
FASES=${*:-edicion requisitos ejecucion validacion grande resultados excel proyecto}
mkdir -p "$(dirname "$DESTINO")"
for FASE in $FASES; do
  PUERTO=$((8800 + RANDOM % 100))
  REGISTRO=$(mktemp)
  "$REPO/.venv/bin/python" "$DIR/servidor.py" "$REPO" $PUERTO "$DESTINO" > "$REGISTRO" 2>&1 &
  PID=$!
  for _ in $(seq 1 60); do grep -q LISTO "$REGISTRO" && break; sleep 0.5; done
  echo "== $FASE"
  node "$DIR/capturar.js" "$FASE" $PUERTO "$SALIDA" | grep -v "^\s*.\[2m"
  kill $PID
  rm -f "$REGISTRO"
done
