"""CSV Onboarding Sandbox API: validates employee CSVs and loads clean rows into Postgres."""
import os

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from .validator import check_headers, parse_csv, validate_rows

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://onboard:onboard_pw@localhost:5433/onboarding")

app = FastAPI(
    title="CSV Onboarding Sandbox",
    description="Upload an employee CSV. Rows are validated and clean ones are loaded into PostgreSQL.",
    version="1.0.0",
)


def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@app.get("/health")
def health():
    try:
        with get_conn() as conn:
            version = conn.execute("SELECT version() AS v").fetchone()["v"]
        return {"status": "ok", "database": version.split(",")[0]}
    except psycopg.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"database unreachable: {e}")


@app.post("/upload")
async def upload_csv(
    file: UploadFile = File(..., description="CSV with columns: employee_id, full_name, email, department_code, hire_date, hourly_rate"),
    dry_run: bool = Query(False, description="Validate only; do not write employee rows"),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="file must be a .csv")

    try:
        headers, rows = parse_csv(await file.read())
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="file must be UTF-8 encoded")

    header_errors = check_headers(headers)
    if header_errors:
        raise HTTPException(status_code=422, detail=header_errors)

    with get_conn() as conn:
        depts = {r["code"] for r in conn.execute("SELECT code FROM departments")}
        accepted, rejected = validate_rows(rows, depts)

        # Emails already used by a different employee_id in the database would violate UNIQUE.
        if accepted:
            existing = conn.execute(
                "SELECT employee_id, email FROM employees WHERE email = ANY(%s)",
                ([r["email"] for r in accepted],),
            ).fetchall()
            taken = {e["email"]: e["employee_id"] for e in existing}
            still_ok = []
            for r in accepted:
                owner = taken.get(r["email"])
                if owner is not None and owner != r["employee_id"]:
                    rejected.append({"line": None, "employee_id": str(r["employee_id"]),
                                     "errors": [f"email already belongs to employee {owner}"]})
                else:
                    still_ok.append(r)
            accepted = still_ok

        if not dry_run and accepted:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO employees (employee_id, full_name, email, department_code, hire_date, hourly_rate)
                    VALUES (%(employee_id)s, %(full_name)s, %(email)s, %(department_code)s, %(hire_date)s, %(hourly_rate)s)
                    ON CONFLICT (employee_id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        email = EXCLUDED.email,
                        department_code = EXCLUDED.department_code,
                        hire_date = EXCLUDED.hire_date,
                        hourly_rate = EXCLUDED.hourly_rate,
                        updated_at = now()
                    """,
                    accepted,
                )

        log = conn.execute(
            """INSERT INTO import_log (filename, dry_run, total_rows, accepted_rows, rejected_rows)
               VALUES (%s, %s, %s, %s, %s) RETURNING import_id""",
            (file.filename, dry_run, len(rows), len(accepted), len(rejected)),
        ).fetchone()

    return {
        "import_id": log["import_id"],
        "filename": file.filename,
        "dry_run": dry_run,
        "total_rows": len(rows),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "rejected_rows": sorted(rejected, key=lambda r: r["line"] or 10**9),
    }


@app.get("/employees")
def list_employees(department: str | None = None):
    sql = """SELECT e.employee_id, e.full_name, e.email, d.name AS department, e.hire_date, e.hourly_rate
             FROM employees e JOIN departments d ON d.code = e.department_code"""
    params = []
    if department:
        sql += " WHERE e.department_code = %s"
        params.append(department.upper())
    sql += " ORDER BY e.employee_id"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


@app.get("/summary")
def department_summary():
    with get_conn() as conn:
        return conn.execute(
            """SELECT d.code, d.name, COUNT(e.employee_id) AS headcount,
                      ROUND(AVG(e.hourly_rate), 2) AS avg_hourly_rate
               FROM departments d LEFT JOIN employees e ON e.department_code = d.code
               GROUP BY d.code, d.name ORDER BY d.code"""
        ).fetchall()


@app.get("/imports")
def import_history():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM import_log ORDER BY import_id DESC LIMIT 20").fetchall()
