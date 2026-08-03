from __future__ import annotations

import sqlite3
from pathlib import Path

import db
import webapp


def _insert_project(project_id: str, *, title: str = "Dashboard <script>alert(1)</script>") -> None:
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO projects
            (id, platform, title, url, description, is_free_to_bid, match_score, proposal_text,
             suggested_price_brl, estimated_hours, ai_reasoning, status, status_changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                project_id,
                "workana",
                title,
                "https://example.com/projeto",
                "Preciso de dashboard Power BI com indicadores de vendas, Power Query e validação dos números.",
                1,
                88,
                "Olá!\n\nProposta completa preservada com quebras de linha.",
                2400,
                27,
                "Estimativa baseada em 27 horas.",
                "proposta_gerada",
            ),
        )


def _client(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    webapp.app.config.update(TESTING=True)
    return webapp.app.test_client()


def test_view_model_retorna_camadas_sem_chamar_groq(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _insert_project("p1")
    project = db.get_project("p1")

    view = webapp.build_project_view_model(project)

    assert view["intelligence"]["category"] in {"Power BI", "Dashboard"}
    assert view["strategy"]
    assert view["pricing"]["suggested_price_brl"] == 2400
    assert view["pricing"]["estimated_hours"] == 27
    assert view["proposal"]["short_proposal_text"]
    assert client is not None


def test_view_model_fallback_legado_funciona(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("falhou")

    monkeypatch.setattr(webapp, "build_proposal_intelligence", fail)

    view = webapp.build_project_view_model(
        {
            "id": "legacy",
            "title": "Projeto legado",
            "proposal_text": "Texto legado",
            "suggested_price_brl": 900,
            "estimated_hours": 12,
        }
    )

    assert view["proposal"]["proposal_text"] == "Texto legado"
    assert view["pricing"]["suggested_price_brl"] == 900


def test_api_proposal_json_valido_sem_dados_sensiveis(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _insert_project("p2")

    response = client.get("/api/project/p2/proposal")
    data = response.get_json()

    assert response.status_code == 200
    assert data["ok"] is True
    assert data["short_proposal_text"]
    assert data["proposal_text"]
    assert "pricing" in data
    assert "intelligence" in data
    assert "knowledge" not in data
    assert "GROQ_API_KEY" not in response.get_data(as_text=True)


def test_api_projeto_inexistente_retorna_404(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/project/nao-existe/proposal")

    assert response.status_code == 404


def test_tela_detalhe_renderiza_propostas_preco_horas_e_escapa_html(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _insert_project("p3")

    response = client.get("/project/p3")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Proposta curta" in html
    assert "Proposta completa" in html
    assert "R$ 2400" in html
    assert "27h" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert 'target="_blank" rel="noopener noreferrer"' in html


def test_tela_nao_renderiza_botao_de_case_sem_url(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _insert_project("p4", title="Ajuste simples em Excel")

    response = client.get("/project/p4")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href=""' not in html


def test_rotas_antigas_pdf_e_status_continuam_funcionando(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _insert_project("p5")

    pdf = client.get("/api/proposal/p5/pdf")
    status = client.post("/api/status/p5", json={"status": "enviado"})

    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF")
    assert status.status_code == 200
    assert status.get_json()["ok"] is True
    assert db.get_project("p5")["status"] == "enviado"


def test_javascript_copia_tem_clipboard_e_fallback() -> None:
    template = Path("templates/dashboard.html").read_text(encoding="utf-8")
    detail = Path("templates/project_detail.html").read_text(encoding="utf-8")

    assert "navigator.clipboard" in template
    assert "document.execCommand('copy')" in template
    assert "Copiado" in template
    assert "navigator.clipboard" in detail
    assert "document.execCommand('copy')" in detail
