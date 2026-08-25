#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 22.04/24.04 EC2 instance.
#
#   curl -fsSL https://raw.githubusercontent.com/abidraza5594/Paper-Signal/main/infra/setup-ec2.sh | bash
#
# Safe to re-run. Does not touch backend/.env if it already exists.

set -euo pipefail

REPO="https://github.com/abidraza5594/Paper-Signal.git"
APP_DIR="$HOME/Paper-Signal"

echo "==> System packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3.11 python3.11-venv python3-pip git curl debian-keyring \
	debian-archive-keyring apt-transport-https

echo "==> Swap (a 1 GB free-tier box cannot render PDFs without it)"
if [ ! -f /swapfile ]; then
	sudo fallocate -l 2G /swapfile
	sudo chmod 600 /swapfile
	sudo mkswap /swapfile
	sudo swapon /swapfile
	echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
	echo "    2 GB swap enabled"
else
	echo "    swap already present"
fi

echo "==> Caddy (automatic HTTPS)"
if ! command -v caddy >/dev/null; then
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
		| sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
		| sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
	sudo apt-get update -qq
	sudo apt-get install -y -qq caddy
fi

echo "==> Application"
if [ -d "$APP_DIR/.git" ]; then
	git -C "$APP_DIR" pull --ff-only
else
	git clone --depth 1 "$REPO" "$APP_DIR"
fi

cd "$APP_DIR/backend"
python3.11 -m venv .venv 2>/dev/null || true
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
	cp .env.example .env
	echo
	echo "    backend/.env created from the example. Edit it now:"
	echo "      MISTRAL_API_KEYS=<your key>"
	echo "      REQUIRE_API_KEY=true"
	echo "      ADMIN_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
	echo "      LOCAL_WORKER_COUNT=2      # 1 GB RAM cannot run 10"
	echo "      CORS_ORIGINS=https://your-host"
fi

sudo mkdir -p /var/www/papersignal
sudo chown -R "$USER":"$USER" /var/www/papersignal

echo "==> systemd service"
sudo cp "$APP_DIR/infra/papersignal.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable papersignal

echo
echo "Done. Next:"
echo "  1. nano $APP_DIR/backend/.env          # add the values printed above"
echo "  2. sudo nano /etc/caddy/Caddyfile      # copy infra/Caddyfile, set your hostname"
echo "  3. sudo systemctl restart papersignal caddy"
echo "  4. From your laptop, upload the Angular build (see DEPLOYMENT.md step 6)"
