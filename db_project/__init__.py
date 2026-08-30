"""
db_project — standalone data-ingestion + database-connection manager.

One job: manage per-project data sources (SQL, NoSQL, file uploads — with
optional VPN/SSH-tunnel access), load any of them into a pandas DataFrame,
and optionally write that DataFrame straight into a target database table.

Quickstart
----------
    from db_project.manager import ProjectManager

    pm = ProjectManager()
    pm.create_project("acme")

    # 1) Register a normal SQL connection
    pm.add_sql_source("acme", "warehouse", dialect="postgres",
                       host="db.acme.com", port=5432, database="warehouse",
                       username="svc", password="secret")

    # 2) Register a VPN/bastion-only SQL connection
    pm.add_sql_source("acme", "internal_mysql", dialect="mysql",
                       host="10.0.4.12", port=3306, database="app",
                       username="svc", password="secret",
                       tunnel={"ssh_host": "bastion.acme.com",
                               "ssh_username": "deploy",
                               "ssh_pkey_path": "/secrets/id_rsa"})

    # 3) Upload a CSV/XLSX/JSON/Parquet file into the project
    path = pm.save_upload("acme", "ratings.csv", raw_bytes)

    # 4) Convert that upload into a real table in a target DB connection
    pm.upload_to_database("acme", "ratings.csv", target_source="warehouse",
                           table_name="ratings", if_exists="replace")
"""
from .manager import ProjectManager

__all__ = ["ProjectManager"]
