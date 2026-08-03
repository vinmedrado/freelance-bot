from __future__ import annotations

from copy import deepcopy
from typing import Any

import project_validation
from project_validation import (
    WARNING_CATEGORY_FALLBACK,
    WARNING_DELIVERABLES_REBUILT,
    WARNING_HEADLINE_REBUILT,
    WARNING_HOURS_FALLBACK,
    WARNING_MISSING_TECHNOLOGIES,
    WARNING_PRICE_FALLBACK,
    WARNING_PROPOSAL_REBUILT,
    validate_project_output,
)


def _base() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    project = {
        "id": "p1",
        "platform": "Workana",
        "title": "Dashboard Power BI para vendas",
        "description": "Preciso de um dashboard Power BI com dados de vendas, DAX e Power Query.",
        "skills": ["Power BI", "DAX", "Power Query"],
        "budget_text": "R$ 2.500",
        "suggested_price_brl": 2400,
        "estimated_hours": 27,
    }
    intelligence = {
        "category": "Power BI",
        "problem_summary": "Criar dashboard de vendas.",
        "client_goal": "Acompanhar indicadores comerciais.",
        "complexity": "medium",
        "scope_confidence": 0.82,
        "relevant_technologies": ["Power BI", "DAX", "Power Query"],
        "deliverables": ["Dashboard Power BI", "Indicadores validados"],
        "risks": [],
        "clarifying_questions": [],
    }
    strategy = {"proof_points": ["Experiência com dashboards corporativos"], "relevant_cases": []}
    pricing = {
        "suggested_price_brl": 2400,
        "estimated_hours": 27,
        "pricing_reason": "Estimativa baseada em dashboard e validação.",
        "confidence": 0.85,
    }
    proposal = {
        "headline": "Dashboard Power BI para análise clara dos indicadores",
        "executive_summary": "Resumo objetivo.",
        "proposed_solution": "Validar dados, modelar e construir o dashboard.",
        "deliverables": ["Dashboard Power BI funcional", "Indicadores validados", "Orientação básica de uso"],
        "technologies": ["Power BI", "DAX"],
        "investment_summary": "O investimento sugerido é de R$ 2.400, considerando aproximadamente 27 horas de trabalho.",
        "proposal_text": "Olá! Posso construir o dashboard com validação dos indicadores e orientação de uso.",
        "short_proposal_text": "Posso construir o dashboard Power BI com validação dos indicadores.",
    }
    return project, intelligence, strategy, pricing, proposal


def test_preco_zero_usa_investment_summary() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    project["suggested_price_brl"] = 0
    pricing["suggested_price_brl"] = 0
    proposal["investment_summary"] = "O investimento sugerido é de R$ 700, considerando aproximadamente 10 horas de trabalho."

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["pricing"]["suggested_price_brl"] == 700
    assert result["normalized"]["project"]["suggested_price_brl"] == 700
    assert WARNING_PRICE_FALLBACK in result["warnings"]


def test_horas_zero_usa_investment_summary() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    project["estimated_hours"] = 0
    pricing["estimated_hours"] = 0
    proposal["investment_summary"] = "O investimento sugerido é de R$ 2.400, considerando aproximadamente 12 horas de trabalho."

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["pricing"]["estimated_hours"] == 12
    assert result["normalized"]["project"]["estimated_hours"] == 12
    assert WARNING_HOURS_FALLBACK in result["warnings"]


def test_categoria_vazia_recebe_fallback() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    intelligence["category"] = ""

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["intelligence"]["category"] not in {"", "unknown", "desconhecida"}
    assert result["normalized"]["project"]["category"]
    assert WARNING_CATEGORY_FALLBACK in result["warnings"]


def test_headline_generica_e_reconstruida() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    proposal["headline"] = "Solução objetiva para o projeto consiste no desenvolvimento de uma ferramenta muito longa e genérica"

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    headline = result["normalized"]["proposal"]["headline"]
    assert headline == "Dashboard Power BI para análise clara dos indicadores"
    assert WARNING_HEADLINE_REBUILT in result["warnings"]


def test_entregaveis_vazios_sao_reconstruidos() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    proposal["deliverables"] = []

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert len(result["normalized"]["proposal"]["deliverables"]) >= 3
    assert "Dashboard Power BI funcional" in result["normalized"]["proposal"]["deliverables"]
    assert WARNING_DELIVERABLES_REBUILT in result["warnings"]


def test_tecnologias_vazias_usam_intelligence_e_skills() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    proposal["technologies"] = []

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["proposal"]["technologies"][:2] == ["Power BI", "DAX"]
    assert WARNING_MISSING_TECHNOLOGIES not in result["warnings"]


def test_tecnologias_ausentes_nao_inventam_generico() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    project["skills"] = []
    intelligence["relevant_technologies"] = []
    proposal["technologies"] = []

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["proposal"]["technologies"] == []
    assert WARNING_MISSING_TECHNOLOGIES in result["warnings"]


def test_proposal_text_vazio_reconstroi_sem_groq(monkeypatch) -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    proposal["proposal_text"] = ""

    def fake_rebuild(*_: Any) -> dict[str, Any]:
        rebuilt = deepcopy(proposal)
        rebuilt["proposal_text"] = "Proposta completa reconstruída deterministicamente."
        rebuilt["short_proposal_text"] = "Proposta curta reconstruída."
        return rebuilt

    monkeypatch.setattr(project_validation, "_rebuild_proposal", fake_rebuild)
    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["proposal"]["proposal_text"] == "Proposta completa reconstruída deterministicamente."
    assert WARNING_PROPOSAL_REBUILT in result["warnings"]


def test_short_proposal_text_vazio_reconstroi() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    proposal["short_proposal_text"] = ""

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["proposal"]["short_proposal_text"]
    assert WARNING_PROPOSAL_REBUILT in result["warnings"]


def test_inconsistencia_entre_preco_e_summary_e_corrigida() -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    proposal["investment_summary"] = "O investimento sugerido é de R$ 900, considerando aproximadamente 10 horas de trabalho."

    result = validate_project_output(project, intelligence, strategy, pricing, proposal)
    summary = result["normalized"]["proposal"]["investment_summary"]

    assert "R$ 2.400" in summary
    assert "27 horas" in summary
    assert result["normalized"]["project"]["suggested_price_brl"] == result["normalized"]["pricing"]["suggested_price_brl"]


def test_projeto_completamente_valido() -> None:
    result = validate_project_output(*_base())

    assert result["is_valid"] is True
    assert result["severity"] == "ok"
    assert result["warnings"] == []


def test_determinismo() -> None:
    args = _base()

    assert validate_project_output(*deepcopy(args)) == validate_project_output(*deepcopy(args))


def test_fallback_sem_groq_quando_rebuild_falha(monkeypatch) -> None:
    project, intelligence, strategy, pricing, proposal = _base()
    proposal["proposal_text"] = ""
    proposal["short_proposal_text"] = ""

    monkeypatch.setattr(project_validation, "_rebuild_proposal", lambda *_: None)
    result = validate_project_output(project, intelligence, strategy, pricing, proposal)

    assert result["normalized"]["proposal"]["proposal_text"]
    assert result["normalized"]["proposal"]["short_proposal_text"]
    assert WARNING_PROPOSAL_REBUILT in result["warnings"]
