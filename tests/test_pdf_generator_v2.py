from __future__ import annotations

import re
from typing import Any

from commercial_strategy import build_commercial_strategy
from knowledge_engine import load_knowledge
from pdf_generator import create_proposal_pdf, resolve_pdf_data, sanitize_pdf_text
from pricing_engine import calculate_pricing
from proposal_generator_v2 import generate_proposal
from proposal_intelligence import build_proposal_intelligence


PROFILE = {
    "nome": "Vinicius Medrado",
    "titulo": "Analista de Dados e Automação",
    "links": {"github": "https://github.com/vinmedrado"},
}


def _page_count(pdf_bytes: bytes) -> int:
    return pdf_bytes.count(b"/Type /Page") - pdf_bytes.count(b"/Type /Pages")


def _text(pdf_bytes: bytes) -> str:
    return pdf_bytes.decode("latin-1", errors="ignore")


def _structured_project(project: dict[str, Any]) -> dict[str, Any]:
    knowledge = load_knowledge()
    intelligence = build_proposal_intelligence(project)
    strategy = build_commercial_strategy(project, intelligence, knowledge)
    pricing = calculate_pricing(project, intelligence, strategy, knowledge)
    proposal = generate_proposal(project, intelligence, strategy, pricing, knowledge)
    return {
        **project,
        **proposal,
        "structured_proposal": proposal,
        "pricing": pricing,
        "suggested_price_brl": pricing["suggested_price_brl"],
        "estimated_hours": pricing["estimated_hours"],
    }


def _format_money(value: Any) -> str:
    return f"R$ {float(value):,.0f}".replace(",", ".")


def _has_zero_hours(content: str) -> bool:
    return bool(re.search(r"(?<!\d)0\s+horas\b", content))


def test_pdf_comeca_com_pdf_e_fallback_legado_funciona() -> None:
    project = {
        "id": "legacy",
        "platform": "workana",
        "title": "Proposta legada",
        "proposal_text": "Olá! Posso executar o projeto com validação inicial, desenvolvimento e entrega organizada.",
        "suggested_price_brl": 900,
        "estimated_hours": 12,
        "url": "",
    }

    pdf = create_proposal_pdf(project, PROFILE)
    content = _text(pdf)

    assert pdf.startswith(b"%PDF")
    assert "Proposta legada" in content
    assert "R$ 900" in content
    assert _page_count(pdf) <= 2


def test_preco_topo_e_investment_summary_sao_consistentes() -> None:
    project = _structured_project(
        {
            "id": "pbi-1",
            "platform": "99freelas",
            "title": "Dashboard Power BI para vendas",
            "description": (
                "Tenho dados de vendas em Excel e preciso de um dashboard Power BI com indicadores de faturamento, "
                "ticket médio, produto e vendedor. Também preciso validar os números e deixar fácil de atualizar."
            ),
            "skills": ["Power BI", "Power Query", "DAX"],
            "budget_text": "R$ 2.500",
            "url": "https://example.com/powerbi",
        }
    )

    data = resolve_pdf_data(project, PROFILE)
    pdf = create_proposal_pdf(project, PROFILE)
    content = _text(pdf)
    money = _format_money(data["price"])

    assert data["price"] == project["pricing"]["suggested_price_brl"]
    assert money in data["investment_summary"]
    assert content.count(money) >= 2
    assert not _has_zero_hours(content)
    assert _page_count(pdf) <= 2


def test_nunca_mostra_preco_zero_quando_valor_esta_no_investment_summary() -> None:
    project = {
        "id": "mapa-calor",
        "platform": "workana",
        "title": "Mapa de calor financeiro",
        "description": "Preciso de uma ferramenta para visualizar mapa de calor financeiro do mercado.",
        "suggested_price_brl": 0,
        "estimated_hours": 0,
        "structured_proposal": {
            "headline": "Solução objetiva para o projeto consiste no desenvolvimento de uma ferramenta visual para mercado financeiro",
            "executive_summary": "Criar uma visualização clara para apoiar análise do mercado financeiro.",
            "proposed_solution": "Construção de painel visual com dados organizados e validação final.",
            "deliverables": ["Mapa de calor financeiro", "Validação dos indicadores", "Orientação de uso"],
            "timeline": [{"phase": "Desenvolvimento", "duration": "3 a 5 dias"}],
            "investment_summary": "O investimento sugerido é de R$ 700, considerando aproximadamente 10 horas de trabalho.",
            "next_step": "Validar a fonte de dados e o formato esperado da visualização.",
        },
    }

    data = resolve_pdf_data(project, PROFILE)
    content = _text(create_proposal_pdf(project, PROFILE))

    assert data["price"] == 700
    assert data["hours"] == 10
    assert "R$ 700" in content
    assert "R$ 0" not in content
    assert not _has_zero_hours(content)
    assert not data["headline"].lower().startswith("solução objetiva para")


def test_sem_preco_valido_mostra_estimativa_apos_validacao() -> None:
    project = {
        "id": "sem-preco",
        "platform": "workana",
        "title": "Projeto sem preço",
        "proposal_text": "Projeto a validar antes de estimar investimento.",
        "suggested_price_brl": 0,
        "estimated_hours": 0,
    }

    content = _text(create_proposal_pdf(project, PROFILE))

    assert "Estimativa ap" in content
    assert "R$ 0" not in content
    assert not _has_zero_hours(content)


def test_headline_nao_comeca_com_frase_generica() -> None:
    project = {
        "id": "headline",
        "platform": "workana",
        "title": "Mapa de calor financeiro para análise do mercado",
        "structured_proposal": {
            "headline": "Desenvolvimento de solução objetiva para o projeto consiste em criar ferramenta visual",
            "executive_summary": "Resumo curto.",
            "proposed_solution": "Solução curta.",
            "investment_summary": "O investimento sugerido é de R$ 700, considerando aproximadamente 10 horas.",
        },
    }

    data = resolve_pdf_data(project, PROFILE)

    assert len(data["headline"]) <= 80
    assert not data["headline"].lower().startswith(("solução objetiva para", "desenvolvimento de", "proposta para"))
    assert "descrição truncada" not in data["headline"].lower()


def test_acentos_sao_preservados_na_sanitizacao() -> None:
    text = sanitize_pdf_text("construção, validação, integração — “automação” …")

    assert "construção" in text
    assert "validação" in text
    assert "integração" in text
    assert '"automação"' in text
    assert "-" in text


def test_entregaveis_duplicados_nao_aparecem() -> None:
    project = {
        "id": "dedupe",
        "platform": "workana",
        "title": "Dashboard Power BI",
        "suggested_price_brl": 2400,
        "estimated_hours": 27,
        "structured_proposal": {
            "headline": "Dashboard Power BI para análise clara dos indicadores",
            "executive_summary": "Resumo.",
            "proposed_solution": "Solução.",
            "deliverables": ["Dashboard", "Dashboard Power BI", "Indicadores", "Indicadores validados", "Documentação", "Documentação básica"],
            "investment_summary": "O investimento sugerido é de R$ 2.400, considerando aproximadamente 27 horas.",
        },
    }

    data = resolve_pdf_data(project, PROFILE)
    content = _text(create_proposal_pdf(project, PROFILE))

    assert data["deliverables"] == ["Dashboard Power BI", "Indicadores validados", "Documentação básica"]
    assert "Dashboard" not in [item for item in data["deliverables"] if item != "Dashboard Power BI"]
    assert "Indicadores validados" in content
    assert "Documentação básica" in content


def test_projeto_simples_gera_uma_pagina() -> None:
    project = _structured_project(
        {
            "id": "excel-1",
            "platform": "workana",
            "title": "Ajuste em planilha Excel de controle financeiro",
            "description": "Preciso corrigir fórmulas, organizar entradas e saídas e validar totais mensais.",
            "skills": ["Excel"],
            "budget_text": "R$ 500",
            "url": "https://example.com/excel",
        }
    )

    pdf = create_proposal_pdf(project, PROFILE)

    assert _page_count(pdf) == 1
    assert "PRONTO PARA COME" not in _text(pdf)


def test_projeto_medio_gera_no_maximo_duas_paginas() -> None:
    project = _structured_project(
        {
            "id": "auto-1",
            "platform": "workana",
            "title": "Automação Python para processar arquivos e integrar API",
            "description": "Preciso automatizar a leitura de arquivos Excel, tratar erros, gerar logs e enviar os dados para uma API externa.",
            "skills": ["Python", "API", "Excel"],
            "budget_text": "R$ 3.000",
            "url": "https://example.com/automacao",
        }
    )

    assert _page_count(create_proposal_pdf(project, PROFILE)) <= 2


def test_assinatura_nao_fica_isolada_e_fullstack_fica_em_duas_paginas() -> None:
    project = _structured_project(
        {
            "id": "full-1",
            "platform": "workana",
            "title": "Aplicação full stack para gestão interna",
            "description": (
                "Preciso de uma aplicação web com frontend, backend, banco de dados, login, perfis de usuário, "
                "integração com API externa, telas de cadastro, dashboard e deploy. O escopo ainda precisa ser validado."
            ),
            "skills": ["React", "Python", "FastAPI", "PostgreSQL"],
            "budget_text": "A combinar",
            "url": "https://example.com/fullstack",
        }
    )

    pdf = create_proposal_pdf(project, PROFILE)
    content = _text(pdf)

    assert _page_count(pdf) <= 2
    assert "Vinicius Medrado" in content
    assert "PRONTO PARA COME" not in content


def test_links_nao_quebram_documento() -> None:
    project = {
        "id": "links",
        "platform": "workana",
        "title": "Dashboard com case",
        "suggested_price_brl": 1500,
        "estimated_hours": 20,
        "structured_proposal": {
            "headline": "Dashboard para acompanhamento operacional",
            "executive_summary": "Resumo.",
            "proposed_solution": "Solução.",
            "deliverables": ["Dashboard funcional", "Validação dos indicadores"],
            "relevant_cases": [{"name": "Projeto relacionado", "reason": "Case com problema semelhante.", "url": "https://example.com/case/com/caminho/muito/longo"}],
            "investment_summary": "O investimento sugerido é de R$ 1.500, considerando aproximadamente 20 horas.",
        },
    }

    pdf = create_proposal_pdf(project, PROFILE)

    assert pdf.startswith(b"%PDF")
    assert "Ver projeto" in _text(pdf)
