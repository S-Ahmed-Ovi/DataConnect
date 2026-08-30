# db_project dashboard — Analyst Console

A universal, schema-agnostic dashboard for data analysts. It's a plain React +
Vite frontend that talks to the existing `db_project` FastAPI app (`main.py`)
over HTTP — no backend changes required beyond the CORS middleware already
added to `main.py`.

"Universal" means: nothing in this app is hardcoded to any particular
project's tables or columns. It has four tabs:

- **Connect** — register a new database (or create a project first). Fill in
  dialect, host/port, credentials, and optionally an SSH bastion or Customer
  VPN, then hit "Connect database." This calls
  `POST /projects/{id}/sources/sql` on the existing API — no manual curl or
  Swagger UI needed.
- **Overview** — auto-profiles whichever table you pick: classifies each
  column as **numeric**, **date**, or **categorical** from its SQL type, and
  shows min/avg/max, null %, top values, or a monthly trend.
- **Explore** — a Power BI–style analysis builder: pick a row dimension (and
  optional "break by" second dimension), add any number of measures (count /
  sum / avg / min / max / count-distinct on any column), stack up filters
  (`=`, `≠`, `>`, `<`, contains, is empty…), set sort direction and a row
  limit, and choose bar / line / area / pie / scatter / table. It shows the
  generated SQL and quick KPI totals above the chart.
- **SQL** — run any ad-hoc SQL against the selected source, see a results
  grid, and chart any two returned columns.

Point it at any registered SQL source (Postgres, MySQL/MariaDB, MSSQL, or
SQLite) and the same four tabs work identically, because table/column
discovery uses dialect-appropriate `information_schema` / `sqlite_master` /
`PRAGMA` queries rather than assuming a fixed schema.

## Run it

```bash
npm install
npm run dev
```

Vite prints a local URL (typically `http://localhost:5173`). Open it, enter
your API base URL at the top (defaults to `http://127.0.0.1:8000`, or set
`VITE_API_BASE` — copy `.env.example` to `.env` and edit it), pick a project,
then a source, then a table.

## Requirements on the API side

Used endpoints, all of which already exist in `main.py`:

- `GET /projects`
- `POST /projects` (create a project, used by the **Connect** tab)
- `GET /projects/{project_id}/sources`
- `POST /projects/{project_id}/sources/sql` (register a source, used by the **Connect** tab)
- `DELETE /projects/{project_id}/sources/{name}` (remove a source, from the sidebar's trash icon)
- `POST /projects/{project_id}/sources/{name}/query` (body: `{"sql": "..."}`)

Because it reuses `query_sql`, any source reachable by `db_project` — direct,
over an SSH/Bastion tunnel, or over a Customer VPN — works here too; the
tunnel/VPN lifecycle is already handled transparently by `ProjectManager`.

**CORS**: since this runs in a browser on a different origin/port than the
API, `main.py` must allow cross-origin requests. This is already set up:

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

Before deploying anywhere public, replace `allow_origins=["*"]` with the
actual origin(s) the dashboard is served from.

## Build for production

```bash
npm run build
```

Outputs static files to `dist/` — serve them with any static file host
(nginx, Netlify, S3, etc.) and set `VITE_API_BASE` at build time to point at
your deployed API.

## Notes on the SQL it generates

- Table/column listing branches on the source's registered `dialect`
  (`postgres`, `mysql`/`mariadb`, `mssql`, `sqlite`).
- `LIMIT` vs `TOP` is handled per dialect (MSSQL has no `LIMIT`).
- Date trends are bucketed by month **client-side** after pulling the raw
  date column (capped at 20,000 rows), so this works identically across
  every dialect without relying on engine-specific date-truncation
  functions.
- Identifiers are lightly quoted; this tool is meant for internal/analyst use
  against sources you already trust — it is not hardened against adversarial
  table/column names.
