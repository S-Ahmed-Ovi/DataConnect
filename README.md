# DataConnect

**DataConnect** is a standalone data connectivity and ingestion layer for registering database sources, securely connecting to them, uploading files, and converting uploaded data into database tables or collections.

It supports:

* SQL databases: PostgreSQL, MySQL, MariaDB, MSSQL, SQLite
* NoSQL: MongoDB
* File formats: CSV, Excel, JSON, Parquet
* Direct database connections
* SSH/Bastion tunnels
* Customer VPN connections through WireGuard or OpenVPN
* DataFrame-to-database ingestion
* A FastAPI interface for HTTP-based integration
* A universal React analyst dashboard

> **Looking for the dashboard?**
> See [`dashboard/README.md`](dashboard/README.md) for the universal analyst UI. It connects to the same `main.py` API and works with any registered database source. The dashboard automatically profiles available tables and provides schema browsing, ad-hoc SQL execution, and one-click charting. Nothing in the dashboard is hardcoded to a particular project's schema.

---

## What DataConnect Does

DataConnect provides three core capabilities:

### 1. Register Database Connections

Register SQL or NoSQL sources per project and connect to them through one of three connectivity modes:

```text
                    Database Connection
                            |
                +-----------+-----------+
                |                       |
             Direct               Secure Tunnel
                |                       |
           host:port             +-------+-------+
                                 |               |
                           SSH/Bastion       Customer VPN
                                             WireGuard/OpenVPN
```

Supported connection modes:

* **Direct** — connects directly to the database host and port.
* **SSH/Bastion** — establishes a temporary SSH port-forward through a bastion host.
* **Customer VPN** — brings up a customer-provided WireGuard or OpenVPN interface and connects to the database through its private network address.

A source can use **at most one** of `tunnel` or `vpn`. Registering both for the same source raises `ValueError`.

---

### 2. Upload Data Files

Upload project-specific data in common analytical formats:

* CSV
* Excel
* JSON
* Parquet

Uploaded files are stored under the corresponding project's `uploads/` directory.

---

### 3. Load Data into a Database

Convert an uploaded file or any existing DataFrame into a real table or collection in a registered database connection.

For example:

```python
pm.upload_to_database(
    "acme",
    "ratings.csv",
    target_source="warehouse",
    table_name="ratings",
    if_exists="replace",
)
```

This allows DataConnect to act as an ingestion layer between files, DataFrames, and registered databases.

---

# Installation

Install the base dependencies:

```bash
pip install -r requirements.txt
```

Install only the database drivers required by your project. See `requirements.txt` for the available drivers and optional dependencies.

For SSH/Bastion connectivity, install:

```bash
pip install sshtunnel paramiko
```

Customer VPN connectivity requires system-level tools rather than Python packages:

* `wireguard-tools` for WireGuard
* `openvpn` for OpenVPN

Refer to the VPN section below for additional requirements.

---

# Start the API

DataConnect includes a FastAPI application in `main.py`.

From the repository root:

```bash
uvicorn main:app --reload --port 8000
```

Then open the Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

---

# Project Storage

DataConnect stores project configuration and uploaded files using the following structure:

```text
projects/
└── {project_id}/
    ├── config.json
    └── uploads/
        └── ...
```

Where:

* `config.json` contains registered connection metadata.
* `uploads/` contains raw files uploaded for that project.
* Secrets can be provided through environment variables instead of storing them in `config.json`.

---

# Quickstart

## 1. Create a Project

```python
from DataConnect.manager import ProjectManager

pm = ProjectManager()

pm.create_project("acme")
```

---

## 2. Register a Direct SQL Connection

```python
pm.add_sql_source(
    "acme",
    "warehouse",
    dialect="postgres",
    host="db.acme.com",
    port=5432,
    database="warehouse",
    username="svc",
    password="secret",
)
```

---

## 3. Register an SQL Connection Through SSH/Bastion

If the database is only reachable through an SSH bastion:

```python
pm.add_sql_source(
    "acme",
    "internal_mysql",
    dialect="mysql",
    host="10.0.4.12",
    port=3306,
    database="app",
    username="svc",
    password="secret",
    tunnel={
        "ssh_host": "bastion.acme.com",
        "ssh_username": "deploy",
        "ssh_pkey_path": "/secrets/id_rsa",
        # Or:
        # "ssh_password": "..."
    },
)
```

DataConnect automatically establishes the SSH tunnel when the connection is used.

Internally, the database connection is redirected through the forwarded local port:

```text
Application
     |
     v
127.0.0.1:<local_port>
     |
     | SSH Tunnel
     v
Bastion Host
     |
     v
10.0.4.12:3306
```

---

## 4. Register an SQL Connection Through Customer VPN

For a database accessible through a customer VPN:

```python
pm.add_sql_source(
    "acme",
    "customer_vpn_db",
    dialect="postgres",
    host="10.50.0.5",
    port=5432,
    database="app",
    username="svc",
    password="secret",
    vpn={
        "vpn_type": "wireguard",
        "config_path": "/secrets/customer_acme.conf",
    },
)
```

The VPN configuration is supplied by the customer or network team.

Unlike SSH tunneling, DataConnect does **not** rewrite the database host and port.

The connection remains:

```text
10.50.0.5:5432
```

The VPN interface simply makes that private address routable.

---

## 5. Register a NoSQL Connection

For MongoDB:

```python
pm.add_nosql_source(
    "acme",
    "events",
    engine="mongodb",
    host="mongo.acme.com",
    port=27017,
    database="events",
)
```

---

## 6. Upload a File

```python
with open("ratings.csv", "rb") as f:
    pm.save_upload(
        "acme",
        "ratings.csv",
        f.read(),
    )
```

---

## 7. Convert the Upload into a Database Table

```python
pm.upload_to_database(
    "acme",
    "ratings.csv",
    target_source="warehouse",
    table_name="ratings",
    if_exists="replace",
)
```

---

## 8. Query Data

SQL sources return query results as a DataFrame:

```python
df = pm.query_sql(
    "acme",
    "warehouse",
    "SELECT * FROM ratings LIMIT 10",
)
```

MongoDB collections can be fetched similarly:

```python
df2 = pm.fetch_nosql(
    "acme",
    "events",
    collection="clicks",
    limit=100,
)
```

---

# Secure Connection Handling

SSH and VPN connections are managed transparently by DataConnect.

Operations such as:

```python
pm.query_sql(...)
pm.upload_to_database(...)
```

automatically handle the required secure connection.

## SSH/Bastion

For SSH-based sources:

1. Establish the SSH connection.
2. Create a local port forward.
3. Rewrite the database connection to `127.0.0.1:<local_port>`.
4. Perform the requested database operation.
5. Close the SSH tunnel.

## Customer VPN

For VPN-based sources:

1. Start the customer-provided VPN configuration.
2. Wait for the VPN interface to become available.
3. Connect to the database using its original private host and port.
4. Perform the requested operation.
5. Tear down the VPN connection.

This behavior applies to both SQL and NoSQL sources where the corresponding connector supports the configured connection mode.

---

# SSH vs Customer VPN

The two secure connection methods work differently.

| Feature                      | SSH/Bastion                   | Customer VPN                 |
| ---------------------------- | ----------------------------- | ---------------------------- |
| Connection mechanism         | SSH port forwarding           | Network-level VPN interface  |
| Database host rewritten      | Yes                           | No                           |
| Database address             | `127.0.0.1:<local_port>`      | Original private address     |
| Requires bastion             | Yes                           | No                           |
| Requires customer VPN config | No                            | Yes                          |
| Typical tools                | `sshtunnel`, `paramiko`       | `wireguard-tools`, `openvpn` |
| Scope                        | Specific forwarded connection | Network-level routing        |

---

# Environment-Based Secrets

Credentials do not have to be stored directly in `config.json`.

The following fields can be supplied through environment variables:

* `username`
* `password`
* `tunnel.ssh_password`

The environment-variable format is:

```text
{PROJECT_ID}__{SOURCE_NAME}__PASSWORD
{PROJECT_ID}__{SOURCE_NAME}__SSH_PASSWORD
```

For example:

```text
ACME__WAREHOUSE__PASSWORD
ACME__WAREHOUSE__SSH_PASSWORD
```

This allows credentials to remain outside the project's configuration file.

---

# File Structure

```text
DataConnect/
│
├── db_project/
│   ├── config.py
│   ├── manager.py
│   │
│   └── connectors/
│       ├── sql.py
│       ├── nosql.py
│       ├── files.py
│       ├── tunnel.py
│       └── vpn.py
│
├── dashboard/
│   ├── ...
│   └── README.md
│
├── main.py
├── requirements.txt
└── README.md
```

### Core Modules

| File                              | Purpose                                                                                                                                             |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `db_project/config.py`            | Defines `ProjectConfig`, `SourceConfig`, `SSHTunnelConfig`, and `VPNConfig`. Handles configuration loading, saving, and connection-mode derivation. |
| `db_project/connectors/sql.py`    | Dialect-agnostic SQL connector supporting PostgreSQL, MySQL, MariaDB, MSSQL, and SQLite. Provides query and DataFrame write operations.             |
| `db_project/connectors/nosql.py`  | MongoDB connector for fetching collections and writing DataFrames.                                                                                  |
| `db_project/connectors/files.py`  | Loads CSV, Excel, JSON, and Parquet files into DataFrames.                                                                                          |
| `db_project/connectors/tunnel.py` | SSH/Bastion tunnel context manager with local port forwarding.                                                                                      |
| `db_project/connectors/vpn.py`    | Customer VPN context manager for WireGuard and OpenVPN.                                                                                             |
| `db_project/manager.py`           | Main public interface through `ProjectManager`.                                                                                                     |
| `main.py`                         | FastAPI application exposing DataConnect functionality over HTTP. Includes CORS support for the dashboard.                                          |
| `dashboard/`                      | React + Vite universal analyst dashboard.                                                                                                           |

---

# Running the API and Dashboard

DataConnect can run as two independent processes.

## 1. Start the FastAPI Backend

From the repository root:

```bash
pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

## 2. Start the Dashboard

Open a second terminal:

```bash
cd dashboard

npm install

npm run dev
```

Vite will print the local dashboard URL, typically:

```text
http://localhost:5173
```

The dashboard communicates with the FastAPI backend through the existing API endpoints.

Currently, it uses:

```text
GET  /projects
GET  /projects/{id}/sources
POST /projects/{id}/sources/{name}/query
```

No additional backend endpoints are required for the current dashboard functionality.

CORS support is already enabled in `main.py` so the React frontend can communicate with the API from a different origin.

---

# Universal Analyst Dashboard

The `dashboard/` application is intentionally schema-agnostic.

It can work against any registered supported source without requiring project-specific schema definitions.

The dashboard provides:

* Project selection
* Database source browsing
* Schema discovery
* Table exploration
* Automatic data profiling
* Ad-hoc SQL execution
* Data previews
* Manual chart configuration
* One-click chart generation

The dashboard does **not** assume a fixed database schema.

For dashboard-specific setup and architecture, see:

[`dashboard/README.md`](dashboard/README.md)

---

# Customer VPN Configuration

DataConnect does **not** generate, manage, or store customer VPN credentials or private keys.

The customer or network administrator provides a ready-to-use VPN configuration file.

The source configuration references that file through:

```python
vpn={
    "vpn_type": "wireguard",
    "config_path": "/secrets/customer_acme.conf",
}
```

Supported VPN types:

```text
wireguard
openvpn
```

---

## WireGuard

A WireGuard configuration is typically provided as a `.conf` file containing the required interface and peer configuration, such as:

* Private key
* Peer public key
* Allowed IPs
* Endpoint
* Interface/network settings

DataConnect uses the system's `wg-quick` tooling to bring the interface up and down.

Typical commands used by the underlying system are equivalent to:

```bash
wg-quick up <config>
wg-quick down <config>
```

---

## OpenVPN

OpenVPN configurations are typically provided as:

```text
.ovpn
```

or:

```text
.conf
```

The configuration may reference a separate credentials file through `auth_user_pass`.

DataConnect uses the system `openvpn` executable to establish the connection.

---

## VPN System Requirements

VPN support requires system-level packages and permissions.

### WireGuard

Install:

```text
wireguard-tools
```

### OpenVPN

Install:

```text
openvpn
```

These are **not Python packages** and therefore are not installed with

```bash
pip install -r requirements.txt
```

Depending on the operating system and environment, bringing up or tearing down a VPN interface may require elevated privileges.

The `VPNConfig` configuration supports operational controls such as:

* `use_sudo`
* `up_timeout`
* `verify_connect_host`
* `verify_connect_port`
* VPN type
* VPN configuration path
* OpenVPN credential configuration

Refer to `db_project/config.py` for the complete `VPNConfig` definition.

---

# Design Principles

DataConnect is designed around a few core principles:

### Database Agnostic

Applications interact with a common interface instead of implementing separate connection logic for every database engine.

### Connection Agnostic

The same source can be accessed through:

```text
Direct
SSH/Bastion
Customer VPN
```

without changing the higher-level query or ingestion API.

### Project Scoped

Connections and uploaded files are organized by project:

```text
Project
 ├── Sources
 └── Uploads
```

### DataFrame Centric

Files and database results can be represented as Pandas DataFrames, making it straightforward to move data between ingestion, transformation, and database layers.

### Secure by Design

Credentials can be supplied through environment variables, while SSH and VPN connectivity is handled through dedicated connection managers.

### Schema Agnostic

The core library and dashboard do not depend on a specific business schema or application.

---

# API + Library Architecture

At a high level:

```text
                    Client Applications
                           |
                +----------+----------+
                |                     |
          Python API             FastAPI
          ProjectManager            |
                |                   |
                +---------+---------+
                          |
                   DataConnect Core
                          |
             +------------+------------+
             |            |            |
            SQL         NoSQL        Files
             |            |            |
      PostgreSQL       MongoDB      CSV/Excel
      MySQL            ...          JSON/Parquet
      MariaDB
      MSSQL
      SQLite
             |
       +-----+------+
       |            |
    Direct     Secure Access
                   |
             +-----+------+
             |            |
          SSH/Bastion   Customer VPN
                         |
                  WireGuard/OpenVPN
```

The React dashboard sits on top of the FastAPI layer and consumes the same DataConnect functionality.

---

# Summary

DataConnect provides a standalone interface for:

```text
Register Source
      ↓
Connect Securely
      ↓
Query / Inspect Data
      ↓
Upload Files
      ↓
Convert Files → DataFrame
      ↓
DataFrame → Database Table / Collection
      ↓
Analyze Through API or Dashboard
```

It can be embedded into a larger application or used independently as a lightweight data connectivity and ingestion service.
