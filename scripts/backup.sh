#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=${1:?Uso: bash scripts/backup.sh /diretorio-protegido}
umask 077
mkdir -p "$DEST"
DEST=$(cd "$DEST" && pwd)
FILE="$DEST/visagismo-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
[ ! -e "$FILE" ] || { echo 'Backup já existe'; exit 1; }
trap 'docker compose start app worker >/dev/null' EXIT
docker compose stop app worker
docker compose run --rm --no-deps -T --entrypoint tar app -C /data -czf - . > "$FILE.tmp"
tar -tzf "$FILE.tmp" >/dev/null
mv "$FILE.tmp" "$FILE"
echo "Backup verificado: $FILE"
