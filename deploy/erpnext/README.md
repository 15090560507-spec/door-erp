# ERPNext bridge deployment

ERPNext is deployed as a separate Compose project. Door ERP reaches its Nginx gateway through the shared `erp-gateway` Docker network.

Create the network once on the server:

```bash
sudo docker network create erp-gateway || true
```

For the existing server, this repository includes a safe connection helper. It restarts only Docker services and does not delete Door ERP data or the ERPNext site:

```bash
cd ~/door-erp
chmod +x deploy/erpnext/connect-server.sh
./deploy/erpnext/connect-server.sh /home/ubuntu/erpnext/source
```

Run ERPNext from `~/erpnext/source` with the official Frappe Docker compose files and this repository's override. Its site name must remain `erp.124.223.87.161.nip.io`, matching the ERPNext site already created on the server.

The ERPNext Frappe site keeps its internal name `erp.124.223.87.161.nip.io`, but users should use the temporary IP-based gateway `https://124.223.87.161:8443/`. This avoids TLS resets observed for `nip.io` from some external networks. Door ERP itself uses the internal Docker proxy URL and does not hairpin through the public network.

After creating an ERPNext API key and secret for the bridge user, add these values to `~/door-erp/.env`:

```dotenv
ERPNEXT_ENABLED=true
ERPNEXT_BASE_URL=https://door-https-proxy:8443
ERPNEXT_PUBLIC_URL=https://124.223.87.161:8443
ERPNEXT_API_KEY=...
ERPNEXT_API_SECRET=...
ERPNEXT_VERIFY_TLS=false
```

Then recreate the Door ERP backend. Do not place these secrets in Git or in frontend environment variables.
The current certificate is self-signed and uses an IP/host mismatch for this gateway, so keep `ERPNEXT_VERIFY_TLS=false` until a company domain and trusted certificate are installed. Open TCP port `8443` in the Tencent Cloud security group as well.

Open Door ERP's `生产管理` page and click `测试连接` after restarting the backend. This test uses the backend-only API credentials and reports a safe success or failure message without revealing the key or secret.
