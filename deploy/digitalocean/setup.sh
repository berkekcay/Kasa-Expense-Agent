#!/usr/bin/env bash
# One-time setup of Kasa on a fresh Ubuntu 24.04 DigitalOcean Droplet (x86, at least 2 GB RAM;
# 4 GB recommended). Run as root on the Droplet:
#
#   curl -fsSL https://raw.githubusercontent.com/berkekcay/Kasa-Expense-Agent/main/deploy/digitalocean/setup.sh -o setup.sh
#   less setup.sh        # read it first
#   bash setup.sh
#
# It installs Docker from Docker's apt repository, adds swap, turns on the firewall (SSH,
# HTTP, HTTPS only; SQL Server stays private), clones the repo to /opt/kasa, writes
# deploy/digitalocean/.env with generated passwords and keys (only if .env does not exist),
# and starts everything. Running it again updates the code and restarts; secrets are kept.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/berkekcay/Kasa-Expense-Agent.git}"
APP_DIR="${APP_DIR:-/opt/kasa}"
SWAP_SIZE="${SWAP_SIZE:-2G}"

say() { printf '\n==> %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "run as root (sudo bash setup.sh)"; exit 1; }
[[ "$(uname -m)" == "x86_64" ]] || { echo "SQL Server needs an x86_64 Droplet"; exit 1; }

say "Packages"
apt-get update -y
apt-get install -y ca-certificates curl git ufw openssl

if ! command -v docker >/dev/null 2>&1; then
  say "Docker (official apt repository)"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

if ! swapon --show | grep -q /swapfile; then
  say "Swap ${SWAP_SIZE} (SQL Server and the Next.js build need the headroom)"
  fallocate -l "$SWAP_SIZE" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

say "Firewall: SSH, HTTP and HTTPS only"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

say "Code in ${APP_DIR}"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR/deploy/digitalocean"
mkdir -p backups
chmod 777 backups  # SQL Server runs as uid 10001 inside its container and writes backups here

# Letters and digits only, so the values need no escaping in database URLs, plus an upper,
# a lower and a digit for SQL Server's password policy.
password() { echo "Kx9$(openssl rand -hex 16)"; }

if [[ ! -f .env ]]; then
  say "Generating .env (passwords and keys stay on this server)"
  ip="$(curl -fsS http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address || true)"
  domain="${DOMAIN:-${ip//./-}.sslip.io}"
  fernet="$(openssl rand -base64 32 | tr '+/' '-_')"
  cat > .env <<EOF
DOMAIN=${domain}
ACME_EMAIL=${ACME_EMAIL:-}
MSSQL_SA_PASSWORD=$(password)
KASA_APP_PASSWORD=$(password)
MSSQL_IMAGE_TAG=2022-latest
MSSQL_MEMORY_LIMIT_MB=1536
TOKEN_ENCRYPTION_KEY=${fernet}
AUTH_SECRET=$(openssl rand -hex 32)
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
EOF
  chmod 600 .env
  echo "Wrote ${PWD}/.env for ${domain}. Add GOOGLE_API_KEY there with: nano ${PWD}/.env"
fi

say "Nightly database backup (03:30, keeps 7 days)"
cat > /etc/cron.d/kasa-backup <<EOF
30 3 * * * root ${APP_DIR}/deploy/digitalocean/backup.sh >> /var/log/kasa-backup.log 2>&1
EOF

say "Building and starting (the first build takes several minutes)"
docker compose up -d --build

set -a; . ./.env; set +a
say "Done. Open https://${DOMAIN} (the certificate can take a minute)."
echo "Status: docker compose -f ${PWD}/docker-compose.yml ps"
echo "Logs:   docker compose -f ${PWD}/docker-compose.yml logs -f api"
