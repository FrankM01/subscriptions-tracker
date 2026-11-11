#!/bin/sh
set -eu
set -o pipefail

: "${RDS_HOST:?}" "${BACKUP_BUCKET:?}" "${BACKUP_PREFIX:?}" "${BACKUP_CERT_PEM:?}"
: "${APP_DB_USER:?}" "${APP_DB_PASSWORD:?}" "${KEYCLOAK_DB_USER:?}" "${KEYCLOAK_DB_PASSWORD:?}"
umask 077
printf '%s\n' "$BACKUP_CERT_PEM" > /tmp/backup-cert.pem

export PGHOST="$RDS_HOST" PGPORT=5432 PGSSLMODE=require
for database in subscriptions keycloak; do
  if [ "$database" = subscriptions ]; then
    export PGUSER="$APP_DB_USER" PGPASSWORD="$APP_DB_PASSWORD"
  else
    export PGUSER="$KEYCLOAK_DB_USER" PGPASSWORD="$KEYCLOAK_DB_PASSWORD"
  fi
  output="/tmp/${database}.dump.p7m"
  pg_dump --format=custom --no-owner --no-acl "$database" |
    openssl cms -encrypt -binary -aes-256-cbc -outform DER -out "$output" /tmp/backup-cert.pem
  aws s3 cp "$output" "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/${database}.dump.p7m" --only-show-errors
  rm -f "$output"
  printf 'Encrypted backup uploaded: %s\n' "$database"
done
unset PGPASSWORD
