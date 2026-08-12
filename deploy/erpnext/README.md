# ERPNext bridge deployment

ERPNext is deployed as a separate Compose project. Door ERP reaches it through its public API; the Door ERP Nginx gateway reaches the ERPNext frontend through the shared `erp-gateway` Docker network.

Create the network once on the server:

```bash
sudo docker network create erp-gateway || true
```

Run ERPNext from `~/erpnext/source` with the official Frappe Docker compose files and this repository's override. Its site name must remain `erp.124.223.87.161.nip.io`, matching the ERPNext site already created on the server.

After creating an ERPNext API key and secret for the bridge user, add these values to `~/door-erp/.env`:

```dotenv
ERPNEXT_ENABLED=true
ERPNEXT_BASE_URL=https://erp.124.223.87.161.nip.io
ERPNEXT_PUBLIC_URL=https://erp.124.223.87.161.nip.io
ERPNEXT_API_KEY=...
ERPNEXT_API_SECRET=...
ERPNEXT_VERIFY_TLS=false
```

Then recreate the Door ERP backend. Do not place these secrets in Git or in frontend environment variables.
After a trusted certificate is installed for the ERPNext hostname, change `ERPNEXT_VERIFY_TLS` back to `true`.
