"""
Persistência simples em SQLite.
Guarda projetos já vistos/processados para não gerar proposta duplicada
toda vez que o pipeline rodar.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "freelance_bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    is_free_to_bid INTEGER,
    match_score REAL,
    proposal_text TEXT,
    suggested_price_brl REAL,
    estimated_hours REAL,
    ai_reasoning TEXT,
    status TEXT DEFAULT 'novo',
    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status_changed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn):
    """Adiciona colunas novas em bancos criados por versões anteriores do schema."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
    if "status_changed_at" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN status_changed_at TEXT")
        conn.execute(
            "UPDATE projects SET status_changed_at = first_seen_at "
            "WHERE status_changed_at IS NULL"
        )


def init_db():
    with get_conn() as conn:
        conn.execute(SCHEMA)
        _migrate(conn)


def project_exists(project_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return row is not None


def insert_project(project: dict):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO projects
            (id, platform, title, url, description, is_free_to_bid, match_score, status_changed_at)
            VALUES (:id, :platform, :title, :url, :description, :is_free_to_bid, :match_score, CURRENT_TIMESTAMP)
            """,
            project,
        )


def save_ai_result(project_id: str, proposal_text: str, price_brl: float,
                    hours: float, reasoning: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE projects
            SET proposal_text = ?, suggested_price_brl = ?, estimated_hours = ?,
                ai_reasoning = ?, status = 'proposta_gerada', status_changed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (proposal_text, price_brl, hours, reasoning, project_id),
        )


def mark_status(project_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET status = ?, status_changed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, project_id),
        )


def list_pending():
    """Projetos com proposta gerada, aguardando revisão/envio manual."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM projects WHERE status = 'proposta_gerada' "
            "ORDER BY match_score DESC"
        ).fetchall()


def get_project(project_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None


def reset_db():
    """Limpa todos os projetos e compacta o banco mantendo o schema."""

    # Limpa os registros e encerra a transação.
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("DELETE FROM projects")
        conn.commit()

    # VACUUM precisa ser executado fora de uma transação.
    with sqlite3.connect(
        DB_PATH,
        timeout=10,
        isolation_level=None,
    ) as conn:
        conn.execute("VACUUM")
