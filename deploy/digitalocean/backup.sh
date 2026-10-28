#!/usr/bin/env bash
# Full backup of the kasa database into deploy/digitalocean/backups (cron runs it nightly,
# see setup.sh). Keeps the last 7. Copy them off the Droplet now and then:
#   scp root@<droplet-ip>:/opt/kasa/deploy/digitalocean/backups/kasa-*.bak .
# Restore: docs/DIGITALOCEAN.md.
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ./.env; set +a

name="kasa-$(date +%Y%m%d-%H%M).bak"
docker compose exec -T mssql /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -b \
  -Q "BACKUP DATABASE kasa TO DISK = N'/var/opt/mssql/backup/${name}' WITH INIT, CHECKSUM"
ls -1t backups/kasa-*.bak | tail -n +8 | xargs -r rm --
echo "$(date -Is) backed up ${name}"
