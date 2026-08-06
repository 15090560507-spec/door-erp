# ERPNext Test Deployment

This directory contains the local override for an **independent** ERPNext
Compose project. It does not store ERPNext itself, its database, its uploads,
or secrets in the Door ERP repository.

## Temporary test hostname

The initial test hostname is `erp.124.223.87.161.nip.io`. It is a public
dynamic-DNS convenience hostname, not a long-term production identity. Replace
it with a company-owned `erp.<domain>` before formal rollout.

## IP fallback access

Some networks reset TLS handshakes for dynamic-DNS hostnames. The shared Nginx
gateway also exposes ERPNext through the server IP on TCP `8443`:

```text
https://124.223.87.161:8443
```

Allow inbound TCP `8443` in the Tencent Cloud security group before using this
fallback. It uses the same self-signed bootstrap certificate as Door ERP, so a
browser warning is expected until a company domain and trusted certificate are
configured.

## Server preparation

Run these commands on the Tencent Cloud VM after pulling the Door ERP change:

```bash
cd ~/door-erp
sudo docker network create erp-gateway || true
sudo mkdir -p deploy/nginx/acme
sudo docker compose up -d https-proxy

mkdir -p ~/erpnext
cd ~/erpnext
git clone --depth 1 https://github.com/frappe/frappe_docker.git source
cp ~/door-erp/deploy/erpnext/.env.example .env
cp ~/door-erp/deploy/erpnext/docker-compose.override.yml ./docker-compose.override.yml
```

Edit `~/erpnext/.env` and replace `DB_PASSWORD` with a random secret:

```bash
openssl rand -base64 36
```

## Start the isolated ERPNext services

```bash
cd ~/erpnext/source
docker compose -p erpnext \
  --env-file ../.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f ../docker-compose.override.yml \
  up -d
```

Wait for the configurator to finish, then create the site. Set the generated
ERPNext administrator password in the shell only; do not add it to `.env`.

```bash
export ERPNEXT_ADMIN_PASSWORD='replace-with-a-strong-administrator-password'
read -rsp 'MariaDB root password: ' DB_PASSWORD; echo
docker compose -p erpnext \
  --env-file ../.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f ../docker-compose.override.yml \
  exec backend bench new-site erp.124.223.87.161.nip.io \
  --mariadb-root-password "$DB_PASSWORD" \
  --admin-password "$ERPNEXT_ADMIN_PASSWORD" \
  --install-app erpnext
unset ERPNEXT_ADMIN_PASSWORD DB_PASSWORD
```

## Certificate

Before using the temporary hostname, first confirm it resolves to the VM:

```bash
getent hosts erp.124.223.87.161.nip.io
```

The Nginx configuration initially uses the existing self-signed certificate.
After ERPNext is reachable, request an ACME certificate using the shared webroot
(replace the email address before running the command):

```bash
sudo docker run --rm -it \
  -v ~/door-erp/deploy/nginx/acme:/var/www/acme \
  -v ~/door-erp/deploy/nginx/certs:/etc/letsencrypt \
  certbot/certbot certonly --webroot -w /var/www/acme \
  -d erp.124.223.87.161.nip.io \
  --email you@example.com --agree-tos --no-eff-email
```

Then change the two certificate paths in `deploy/nginx/erpnext.conf` to:

```nginx
ssl_certificate /etc/nginx/certs/live/erp.124.223.87.161.nip.io/fullchain.pem;
ssl_certificate_key /etc/nginx/certs/live/erp.124.223.87.161.nip.io/privkey.pem;
```

Finally reload the existing gateway:

```bash
cd ~/door-erp
sudo docker compose up -d https-proxy
```

If the public `nip.io` hostname cannot obtain a certificate, keep this as an
internal test site and switch to a company-owned domain before rollout.
