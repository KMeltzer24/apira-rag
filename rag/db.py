from contextlib import contextmanager

import psycopg2
from pgvector.psycopg2 import register_vector

from rag.config import DATABASE_URL, psycopg2_dsn


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at the same RDS PostgreSQL instance "
            "as the backend services."
        )
    return DATABASE_URL


@contextmanager
def get_connection():
    conn = psycopg2.connect(psycopg2_dsn(require_database_url()))
    register_vector(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
