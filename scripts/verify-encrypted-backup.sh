#!/bin/bash
set -euo pipefail

backup_dir="${1:?Indica el directorio que contiene la llave y el certificado}"
archive_dir="${2:?Indica el directorio que contiene los archivos cifrados}"
key="$backup_dir/backup-key.pem"
cert="$backup_dir/backup-cert.pem"
container="cb-backup-restore-check-$(date +%s)-$$"

cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --rm -d --name "$container" --network none \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:18-alpine >/dev/null
for attempt in {1..60}; do
  if docker exec -u postgres "$container" pg_isready -q; then break; fi
  if [ "$attempt" -eq 60 ]; then echo 'PostgreSQL temporal no inició.' >&2; exit 1; fi
  sleep 1
done

for database in subscriptions keycloak; do
  docker exec -u postgres "$container" createdb "$database"
  echo "Ingresa la contraseña de la llave para restaurar $database:"
  openssl cms -decrypt -binary -inform DER -in "$archive_dir/$database.dump.p7m" \
    -recip "$cert" -inkey "$key" |
    docker exec -i -u postgres "$container" pg_restore --exit-on-error --no-owner --no-acl -d "$database"
done

version=$(docker exec -u postgres "$container" psql -d subscriptions -Atc 'SELECT version_num FROM alembic_version')
realm=$(docker exec -u postgres "$container" psql -d keycloak -Atc "SELECT name FROM realm WHERE name='subscriptions'")
test "$version" = '406d989e7e68'
test "$realm" = 'subscriptions'
echo 'Restauración local verificada: migración y realm encontrados.'
