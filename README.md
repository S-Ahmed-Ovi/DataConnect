# db_project

A standalone folder whose only job is:

> **Looking for the dashboard?** See [`dashboard/README.md`](dashboard/README.md) — a
> universal analyst UI (React) that talks to this same `main.py` API. It works
> against any registered source (Postgres/MySQL/MSSQL/SQLite), auto-profiles
> whatever tables it finds, and includes an ad-hoc SQL editor with one-click
> charting. Nothing about it is hardcoded to a particular project's schema.

1. Register database connections per project (SQL, NoSQL) — reached
   **Direct**, over an **SSH/Bastion** tunnel, or over a **Customer VPN**
   (WireGuard/OpenVPN):

   ```
   Database Connection
          |
    +-----+-----+
    |           |
  Direct    Secure Tunnel
    |           |
 host:port  +----+----+
            |         |
       SSH/Bastion  Customer VPN
                     (WireGuard/OpenVPN/etc.)
            +----+----+
                 |
                 DB
   ```

2. Accept file uploads (CSV / Excel / JSON / Parquet) per project.
3. Convert an upload — or any DataFrame — into a real table/collection in a
   registered database connection.

No dependency on any larger app. Drop this folder wherever you like. A
`main.py` FastAPI app is included to exercise all of the above over HTTP.

## Install

```bash
pip install -r requirements.txt
# plus whichever DB drivers you actually need (see comments in the file)
# and sshtunnel + paramiko if any source needs an SSH/bastion tunnel
# and, for Customer VPN sources, the SYSTEM packages wireguard-tools
# and/or openvpn (not a pip install — see requirements.txt)
```

## Try it via the API

```bash
uvicorn main:app --reload --port 8000
# then open http://127.0.0.1:8000/docs
```

## Layout it creates

```
projects/
  {project_id}/
    config.json     <- registered connections (secrets can live in env vars instead)
    uploads/         <- raw uploaded files
```

## Quickstart

```python
from db_project.manager import ProjectManager

pm = ProjectManager()
pm.create_project("acme")

# 1. A normal SQL connection
pm.add_sql_source("acme", "warehouse",
    dialect="postgres", host="db.acme.com", port=5432,
    database="warehouse", username="svc", password="secret")

# 2. A SQL connection that's ONLY reachable via an SSH bastion
pm.add_sql_source("acme", "internal_mysql",
    dialect="mysql", host="10.0.4.12", port=3306,
    database="app", username="svc", password="secret",
    tunnel={
        "ssh_host": "bastion.acme.com",
        "ssh_username": "deploy",
        "ssh_pkey_path": "/secrets/id_rsa",   # or ssh_password="..."
    })

# 2b. A SQL connection that's ONLY reachable via a Customer VPN
#     (WireGuard shown; vpn_type="openvpn" also supported)
pm.add_sql_source("acme", "customer_vpn_db",
    dialect="postgres", host="10.50.0.5", port=5432,
    database="app", username="svc", password="secret",
    vpn={
        "vpn_type": "wireguard",
        "config_path": "/secrets/customer_acme.conf",  # pre-made by the customer/network team
    })

# 3. A NoSQL connection
pm.add_nosql_source("acme", "events",
    engine="mongodb", host="mongo.acme.com", port=27017, database="events")

# 4. Upload a file
with open("ratings.csv", "rb") as f:
    pm.save_upload("acme", "ratings.csv", f.read())

# 5. THE CONVERSION STEP — turn the upload into a real table
pm.upload_to_database("acme", "ratings.csv",
    target_source="warehouse", table_name="ratings", if_exists="replace")

# 6. Query anything back out as a DataFrame
df = pm.query_sql("acme", "warehouse", "SELECT * FROM ratings LIMIT 10")
df2 = pm.fetch_nosql("acme", "events", collection="clicks", limit=100)
```

Both secure-tunnel methods are handled transparently — `query_sql` /
`upload_to_database` bring the SSH tunnel or the VPN interface up, connect
through it, and tear it back down again automatically, whether the target
is `sql` or `nosql`. A source may use **at most one** of `tunnel` / `vpn` —
registering both raises `ValueError`.

Note the difference between the two: SSH forwards a **local port**
(`_open_sql`/`_open_nosql` rewrite `host`/`port` to `127.0.0.1:<local>`),
while a VPN interface makes the DB's **real** private address (e.g.
`10.50.0.5:5432`) directly routable — host/port are left untouched.

## Secrets without committing them to config.json

Any `username` / `password` / `tunnel.ssh_password` field can be omitted
from `config.json` and supplied via an environment variable instead:

```
{PROJECT_ID}__{SOURCE_NAME}__PASSWORD
{PROJECT_ID}__{SOURCE_NAME}__SSH_PASSWORD
```

e.g. for project `acme`, source `warehouse`: `ACME__WAREHOUSE__PASSWORD`.

## Files

| File | Purpose |
|---|---|
| `db_project/config.py` | `ProjectConfig` / `SourceConfig` / `SSHTunnelConfig` / `VPNConfig` dataclasses, load/save `config.json`, `connection_mode` derivation |
| `db_project/connectors/sql.py` | Dialect-agnostic SQL connector (postgres/mysql/mariadb/mssql/sqlite) — read via `query()`, write via `write_dataframe()` |
| `db_project/connectors/nosql.py` | MongoDB connector — `fetch_collection()` / `write_dataframe()` |
| `db_project/connectors/files.py` | CSV/Excel/JSON/Parquet → DataFrame |
| `db_project/connectors/tunnel.py` | SSH/Bastion tunnel context manager — forwards a local port |
| `db_project/connectors/vpn.py` | Customer VPN (WireGuard/OpenVPN) context manager — brings the interface up/down via `wg-quick`/`openvpn` |
| `db_project/manager.py` | `ProjectManager` — the class you actually import |
| `main.py` | FastAPI app wrapping `ProjectManager` for testing over HTTP (`/docs` for Swagger UI). Also enables CORS so the `dashboard/` frontend can call it from a different origin. |
| `dashboard/` | Standalone React + Vite frontend: universal analyst dashboard (schema browser, auto-profiling, manual chart builder, ad-hoc SQL editor). See `dashboard/README.md`. |

## Running the API + dashboard together

```bash
# 1. API (from the repo root)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 2. Dashboard (in a second terminal)
cd dashboard
npm install
npm run dev
# open the printed http://localhost:5173 URL
```

The dashboard only calls three existing endpoints — `GET /projects`,
`GET /projects/{id}/sources`, and `POST /projects/{id}/sources/{name}/query` —
so no backend changes are needed beyond the CORS middleware already added to
`main.py`.

## VPN config file (`vpn.config_path`)

`db_project` never generates or stores WireGuard/OpenVPN keys — the
customer/network team hands you a ready-made config file and you just point
`config_path` at it:

- **WireGuard**: a `.conf` file (your private key, the DB-side peer's public
  key + `AllowedIPs`, `Endpoint`, etc.), managed via `wg-quick up|down`.
- **OpenVPN**: a `.ovpn`/`.conf` file, optionally plus a separate
  `auth_user_pass_path` credentials file, run via `openvpn --config ... --daemon`.

Both require host-level tools (`wireguard-tools` / `openvpn`) and normally
root — see `requirements.txt` and `VPNConfig` in `config.py` for every field
(`use_sudo`, `up_timeout`, `verify_connect_host`/`port`, etc.).
