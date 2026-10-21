-- Schema for the CSV onboarding sandbox (sample data only).

CREATE TABLE departments (
    code        VARCHAR(10)  PRIMARY KEY,
    name        VARCHAR(100) NOT NULL
);

CREATE TABLE employees (
    employee_id     INTEGER       PRIMARY KEY,
    full_name       VARCHAR(120)  NOT NULL,
    email           VARCHAR(255)  NOT NULL UNIQUE,
    department_code VARCHAR(10)   NOT NULL REFERENCES departments(code),
    hire_date       DATE          NOT NULL,
    hourly_rate     NUMERIC(8,2)  NOT NULL CHECK (hourly_rate > 0),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Every upload attempt is recorded, including dry runs and rejected rows.
CREATE TABLE import_log (
    import_id     SERIAL       PRIMARY KEY,
    filename      VARCHAR(255) NOT NULL,
    dry_run       BOOLEAN      NOT NULL,
    total_rows    INTEGER      NOT NULL,
    accepted_rows INTEGER      NOT NULL,
    rejected_rows INTEGER      NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
