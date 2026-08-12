#!/usr/bin/env bash
# Connect the existing ERPNext stack to Door ERP's shared Nginx network.
# Run from the Door ERP repository as the normal server user:
# ./deploy/erpnext/connect-server.sh /home/ubuntu/erpnext/source

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ERPNEXT_SOURCE_DIR="${1:-$HOME/erpnext/source}"
ERPNEXT_ROOT="$(cd "$ERPNEXT_SOURCE_DIR/.." && pwd)"
ERP_HOST="erp.124.223.87.161.nip.io"

if [[ ! -f "$ERPNEXT_SOURCE_DIR/compose.yaml" || ! -f "$ERPNEXT_ROOT/.env" ]]; then
  echo "找不到 ERPNext Compose 或 .env：$ERPNEXT_SOURCE_DIR" >&2
  exit 1
fi

sudo docker network create erp-gateway >/dev/null 2>&1 || true
sudo install -m 0644 "$PROJECT_DIR/deploy/erpnext/docker-compose.override.yml" "$ERPNEXT_ROOT/docker-compose.override.yml"

if grep -q '^FRAPPE_SITE_NAME_HEADER=' "$ERPNEXT_ROOT/.env"; then
  sed -i "s|^FRAPPE_SITE_NAME_HEADER=.*|FRAPPE_SITE_NAME_HEADER=$ERP_HOST|" "$ERPNEXT_ROOT/.env"
else
  echo "FRAPPE_SITE_NAME_HEADER=$ERP_HOST" >> "$ERPNEXT_ROOT/.env"
fi

(
  cd "$ERPNEXT_SOURCE_DIR"
  sudo docker compose -p erpnext \
    --env-file ../.env \
    -f compose.yaml \
    -f overrides/compose.mariadb.yaml \
    -f overrides/compose.redis.yaml \
    -f ../docker-compose.override.yml up -d
)

cd "$PROJECT_DIR"
sudo docker compose build backend frontend
sudo docker compose up -d --force-recreate backend frontend https-proxy

echo "验证 Door ERP 主页："
curl -kfsS -o /dev/null -w '  HTTPS %{http_code}\n' https://127.0.0.1/
echo "验证 ERPNext 反向代理："
curl -kfsS -o /dev/null -w '  HTTPS %{http_code}\n' \
  https://127.0.0.1:8443/api/method/ping

echo
echo "网络与代理已连接。ERPNext 公网入口：https://124.223.87.161:8443/"
echo "接着在 Door ERP .env 填入 ERPNEXT_ENABLED、API Key、API Secret，"
echo "然后执行：sudo docker compose up -d --force-recreate backend"
