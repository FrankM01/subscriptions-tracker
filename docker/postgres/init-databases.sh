#!/bin/sh
set -eu

psql \
  --username "$POSTGRES_USER" \
  --dbname postgres \
  --set ON_ERROR_STOP=1 \
  --set APP_DB_USER="$APP_DB_USER" \
  --set APP_DB_PASSWORD="$APP_DB_PASSWORD" \
  --set APP_DB_NAME="$APP_DB_NAME" \
  --set KEYCLOAK_DB_USER="$KEYCLOAK_DB_USER" \
  --set KEYCLOAK_DB_PASSWORD="$KEYCLOAK_DB_PASSWORD" \
  --set KEYCLOAK_DB_NAME="$KEYCLOAK_DB_NAME" \
  --file /docker-entrypoint-initdb.d/10-init-databases.sql
