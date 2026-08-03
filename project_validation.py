"""Validação e normalização central dos dados comerciais do projeto."""
from __future__ import annotations

import copy
import logging
import re
import unicodedata
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

WARNING_PRICE_FALLBACK = "PRICE_FALLBACK_USED"
WARNING_HOURS_FALLBACK = "HOURS_FALLBACK_USED"
WARNING_CATEGORY_FALLBACK = "CATEGORY_FALLBACK_USED"
WARNING_HEADLINE_REBUILT = "HEADLINE_REBUILT"
WARNING_DELIVERABLES_REBUILT = "DELIVERABLES_REBUILT"
WARNING_PROPOSAL_REBUILT = "PROPOSAL_REBUILT"
WARNING_LOW_SCOPE_CONFIDENCE = "LOW_SCOPE_CONFIDENCE"
WARNING_BUDGET_INCOMPATIBLE = "BUDGET_INCOMPATIBLE"
WARNING_MISSING_TECHNOLOGIES = "MISSING_TECHNOLOGIES"

GENERIC_HEADLINE_PREFIXES = (
    "solucao objetiva para",
    "solução objetiva para",
    "o projeto consiste",
    "desenvolvimento de",
    "proposta para",
)


class ValidationResult(TypedDict):
    is_valid: bool
    severity: str
    issues: list[str]
    warnings: list[str]
    normalized: dict[str, dict[str, Any]]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if value is None:
        return {}
    data: dict[str, Any] = {}
    for key in dir(value):
        if key.startswith("_"):
            continue
        try:
            attr = getattr(value, key)
        except Exception:
            continue
        if not callable(attr):
            data[key] = attr
    return data


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _money(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _hours(value: Any) -> int:
    try:
        number = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _extract_money(text: Any) -> float:
    content = _clean(text)
    for raw in re.findall(r"R\$\s*([0-9][0-9\.\,]*)", content):
        number = _money(raw.replace(".", "").replace(",", "."))
        if number:
            return number
    return 0.0


def _extract_hours(text: Any) -> int:
    content = _normalize(text)
    for pattern in (r"aproximadamente (\d{1,4}) horas", r"(\d{1,4}) horas", r"(\d{1,4})h\b"):
        match = re.search(pattern, content)
        if match:
            return _hours(match.group(1))
    return 0


def _format_money(value: float) -> str:
    return f"R$ {value:,.0f}".replace(",", ".")


def _semantic_key(value: str) -> str:
    normalized = _normalize(value)
    groups = {
        "dashboard": ("dashboard power bi", "dashboard", "painel"),
        "indicadores": ("indicadores validados", "indicadores", "kpi"),
        "documentacao": ("documentacao basica", "documentacao", "documentacao de uso"),
        "testes": ("testes", "validacao funcional", "validacao"),
        "api": ("api rest", "api"),
        "modelo_dados": ("modelo de dados", "modelagem de dados"),
        "orientacao": ("orientacao basica de uso", "orientacao de uso", "orientacao"),
    }
    for key, aliases in groups.items():
        if any(alias in normalized for alias in aliases):
            return key
    return normalized


def _dedupe(items: list[Any], limit: int | None = None) -> list[str]:
    by_key: dict[str, str] = {}
    order: list[str] = []
    for raw in items:
        value = _clean(raw)
        if not value:
            continue
        key = _semantic_key(value)
        if key not in by_key:
            by_key[key] = value
            order.append(key)
        elif len(_normalize(value)) > len(_normalize(by_key[key])):
            by_key[key] = value
    result = [by_key[key] for key in order]
    return result[:limit] if limit else result


def _project_text(project: dict[str, Any]) -> str:
    skills = project.get("skills") or []
    return _normalize(" ".join([project.get("title", ""), project.get("description", ""), " ".join(map(str, skills))]))


def _derive_category(project: dict[str, Any]) -> str:
    text = _project_text(project)
    rules = (
        ("Power BI", ("power bi", "dax", "power query", "dashboard")),
        ("Excel", ("excel", "planilha", "vba", "macro")),
        ("Automação", ("automacao", "automatizar", "rotina", "python")),
        ("API", ("api", "webhook", "integracao", "endpoint")),
        ("Web Scraping", ("scraping", "crawler", "raspagem", "playwright", "selenium")),
        ("Full Stack", ("full stack", "frontend", "backend", "react", "sistema web")),
        ("Banco de Dados", ("sql", "postgresql", "sqlite", "banco de dados")),
    )
    for category, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category
    return "Projeto sob medida"


def _valid_category(value: Any) -> bool:
    normalized = _normalize(value)
    return bool(normalized and normalized not in {"none", "unknown", "desconhecida", "nao classificado", "nao classificada"})


def _headline_is_bad(headline: str, project: dict[str, Any]) -> bool:
    normalized = _normalize(headline)
    description = _normalize(project.get("description"))
    return (
        not headline
        or any(normalized.startswith(prefix) for prefix in GENERIC_HEADLINE_PREFIXES)
        or len(headline) > 90
        or headline.rstrip().endswith("...")
        or (description and normalized and normalized in description and len(normalized.split()) > 8)
    )


def _headline(category: str, project: dict[str, Any], intelligence: dict[str, Any]) -> str:
    title = _clean(project.get("title"))
    objective = _clean(intelligence.get("client_goal") or intelligence.get("problem_summary"))
    text = _normalize(" ".join([category, title, objective]))
    if "power bi" in text or "dashboard" in text:
        return "Dashboard Power BI para análise clara dos indicadores"
    if "excel" in text or "planilha" in text:
        return "Planilha Excel organizada para uso claro e confiável"
    if "automacao" in text or "python" in text:
        return "Automação Python para reduzir trabalho manual"
    if "api" in text or "integracao" in text:
        return "Integração estruturada entre sistemas"
    if "full stack" in text or "sistema web" in text:
        return "Aplicação sob medida para organizar o fluxo operacional"
    base = title or objective or category
    return f"{category} para {base}"[:90].rstrip(" ,.;")


def _deliverables_for(category: str) -> list[str]:
    normalized = _normalize(category)
    if normalized in {"power bi", "dashboard"}:
        return ["Dashboard Power BI funcional", "Modelo de dados organizado", "Indicadores validados", "Orientação básica de uso"]
    if normalized == "excel":
        return ["Planilha funcional", "Fórmulas e validações", "Área de entrada e saída organizada", "Orientação de uso"]
    if normalized in {"automacao", "python", "web scraping"}:
        return ["Script ou aplicação funcional", "Tratamento de erros", "Logs básicos", "Documentação de execução"]
    if normalized in {"full stack", "api"}:
        return ["Interface funcional", "Backend/API", "Banco de dados", "Validação dos fluxos"]
    return ["Levantamento do escopo", "Entrega funcional", "Testes de funcionamento"]


def _technologies(project: dict[str, Any], intelligence: dict[str, Any], proposal: dict[str, Any]) -> list[str]:
    values = list(proposal.get("technologies") or [])
    values.extend(intelligence.get("relevant_technologies") or [])
    values.extend(project.get("skills") or [])
    return _dedupe(values, 6)


def _recalculate_pricing(
    project: dict[str, Any],
    intelligence: dict[str, Any],
    strategy: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        from knowledge_engine import load_knowledge
        from pricing_engine import calculate_pricing

        return calculate_pricing(project, intelligence, strategy, load_knowledge())
    except Exception as exc:
        logger.exception("Falha ao recalcular precificação durante validação: %s", exc)
        return None


def _rebuild_proposal(
    project: dict[str, Any],
    intelligence: dict[str, Any],
    strategy: dict[str, Any],
    pricing: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        from knowledge_engine import load_knowledge
        from proposal_generator_v2 import generate_proposal

        return dict(generate_proposal(project, intelligence, strategy, pricing, load_knowledge()))
    except Exception as exc:
        logger.exception("Falha ao reconstruir proposta durante validação: %s", exc)
        return None


def _recalculate_intelligence(project: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from proposal_intelligence import build_proposal_intelligence

        return dict(build_proposal_intelligence(project))
    except Exception as exc:
        logger.exception("Falha ao recalcular inteligência durante validação: %s", exc)
        return None


def _sync_investment_summary(proposal: dict[str, Any], price: Any, hours: Any, warnings: list[str]) -> None:
    numeric_price = _money(price)
    numeric_hours = _hours(hours)
    summary = _clean(proposal.get("investment_summary"))
    summary_price = _extract_money(summary)
    summary_hours = _extract_hours(summary)
    if numeric_price and summary_price and round(summary_price) != round(numeric_price):
        warnings.append("INVESTMENT_SUMMARY_PRICE_SYNCED")
        summary = ""
    if numeric_hours and summary_hours and summary_hours != numeric_hours:
        warnings.append("INVESTMENT_SUMMARY_HOURS_SYNCED")
        summary = ""
    if not summary and numeric_price:
        summary = f"O investimento sugerido é de {_format_money(numeric_price)}"
        if numeric_hours:
            summary += f", considerando aproximadamente {numeric_hours} horas de trabalho."
        else:
            summary += "."
    proposal["investment_summary"] = summary


def validate_project_output(
    project: Any,
    intelligence: dict[str, Any] | None,
    strategy: dict[str, Any] | None,
    pricing: dict[str, Any] | None,
    proposal: dict[str, Any] | None,
) -> ValidationResult:
    """Valida e normaliza os dados usados por persistência, dashboard e PDF."""
    normalized_project = _as_dict(project)
    normalized_intelligence = _as_dict(intelligence)
    normalized_strategy = _as_dict(strategy)
    normalized_pricing = _as_dict(pricing)
    normalized_proposal = _as_dict(proposal)
    issues: list[str] = []
    warnings: list[str] = []

    if not _clean(normalized_project.get("title")):
        normalized_project["title"] = "Projeto sem título"
        issues.append("TITLE_FALLBACK_USED")
    if not _clean(normalized_project.get("description")):
        normalized_project["description"] = "Descrição não informada. Validar escopo antes do envio."
        issues.append("DESCRIPTION_FALLBACK_USED")

    if not _valid_category(normalized_intelligence.get("category")):
        recalculated = _recalculate_intelligence(normalized_project)
        if recalculated:
            normalized_intelligence.update(recalculated)
        if not _valid_category(normalized_intelligence.get("category")):
            normalized_intelligence["category"] = _derive_category(normalized_project)
        warnings.append(WARNING_CATEGORY_FALLBACK)

    category = _clean(normalized_intelligence.get("category") or "Projeto sob medida")
    normalized_project["category"] = category

    price = (
        _money(normalized_pricing.get("suggested_price_brl"))
        or _money(normalized_project.get("suggested_price_brl"))
        or _money(normalized_project.get("valor_sugerido_brl"))
        or _extract_money(normalized_proposal.get("investment_summary"))
    )
    hours = (
        _hours(normalized_pricing.get("estimated_hours"))
        or _hours(normalized_project.get("estimated_hours"))
        or _hours(normalized_project.get("estimativa_horas"))
        or _extract_hours(normalized_proposal.get("investment_summary"))
    )

    if not price or not hours:
        recalculated_pricing = _recalculate_pricing(normalized_project, normalized_intelligence, normalized_strategy)
        if recalculated_pricing:
            normalized_pricing.update(recalculated_pricing)
            price = price or _money(normalized_pricing.get("suggested_price_brl"))
            hours = hours or _hours(normalized_pricing.get("estimated_hours"))

    if price:
        normalized_pricing["suggested_price_brl"] = price
        normalized_project["suggested_price_brl"] = price
    else:
        normalized_pricing["suggested_price_brl"] = "Estimativa após validação"
        normalized_project["suggested_price_brl"] = "Estimativa após validação"
        warnings.append(WARNING_PRICE_FALLBACK)
    if hours:
        normalized_pricing["estimated_hours"] = hours
        normalized_project["estimated_hours"] = hours
    else:
        normalized_pricing["estimated_hours"] = "A confirmar"
        normalized_project["estimated_hours"] = "A confirmar"
        warnings.append(WARNING_HOURS_FALLBACK)

    if price and (_money(project.get("suggested_price_brl") if isinstance(project, dict) else getattr(project, "suggested_price_brl", 0)) != price):
        warnings.append(WARNING_PRICE_FALLBACK)
    if hours and (_hours(project.get("estimated_hours") if isinstance(project, dict) else getattr(project, "estimated_hours", 0)) != hours):
        warnings.append(WARNING_HOURS_FALLBACK)

    headline = _clean(normalized_proposal.get("headline"))
    if _headline_is_bad(headline, normalized_project):
        normalized_proposal["headline"] = _headline(category, normalized_project, normalized_intelligence)
        warnings.append(WARNING_HEADLINE_REBUILT)

    deliverables = _dedupe(list(normalized_proposal.get("deliverables") or []), 6)
    if len(deliverables) < 3:
        deliverables = _dedupe(deliverables + _deliverables_for(category), 6)
        warnings.append(WARNING_DELIVERABLES_REBUILT)
    normalized_proposal["deliverables"] = deliverables[:6]

    technologies = _technologies(normalized_project, normalized_intelligence, normalized_proposal)
    if not technologies:
        warnings.append(WARNING_MISSING_TECHNOLOGIES)
    normalized_proposal["technologies"] = technologies

    needs_proposal = not _clean(normalized_proposal.get("proposal_text")) or not _clean(normalized_proposal.get("short_proposal_text"))
    if needs_proposal:
        rebuilt = _rebuild_proposal(normalized_project, normalized_intelligence, normalized_strategy, normalized_pricing)
        if rebuilt:
            for key, value in rebuilt.items():
                if key not in {"investment_summary"} or not normalized_proposal.get(key):
                    normalized_proposal[key] = value
        warnings.append(WARNING_PROPOSAL_REBUILT)

    if not _clean(normalized_proposal.get("proposal_text")):
        normalized_proposal["proposal_text"] = (
            f"Olá! Entendi que o projeto precisa de uma entrega em {category.lower()}. "
            f"Minha proposta é validar o escopo, desenvolver os entregáveis principais e realizar testes antes da entrega. "
            f"Como próximo passo, podemos alinhar os dados de entrada e os critérios de aceite."
        )
    if not _clean(normalized_proposal.get("short_proposal_text")):
        normalized_proposal["short_proposal_text"] = normalized_proposal["proposal_text"][:700]

    normalized_proposal["headline"] = _clean(normalized_proposal.get("headline")) or _headline(category, normalized_project, normalized_intelligence)
    _sync_investment_summary(
        normalized_proposal,
        normalized_pricing.get("suggested_price_brl"),
        normalized_pricing.get("estimated_hours"),
        warnings,
    )

    scope_confidence = normalized_intelligence.get("scope_confidence")
    try:
        if float(scope_confidence or 0) < 0.62:
            warnings.append(WARNING_LOW_SCOPE_CONFIDENCE)
    except (TypeError, ValueError):
        pass

    budget = _extract_money(normalized_project.get("budget_text"))
    if budget and price and budget < price * 0.6:
        warnings.append(WARNING_BUDGET_INCOMPATIBLE)

    normalized_project.update(
        {
            "headline": normalized_proposal["headline"],
            "structured_proposal": normalized_proposal,
            "proposal_text": normalized_proposal["proposal_text"],
            "short_proposal_text": normalized_proposal["short_proposal_text"],
        }
    )

    unique_warnings = list(dict.fromkeys(warnings))
    severity = "error" if issues else "warning" if unique_warnings else "ok"
    return {
        "is_valid": not issues,
        "severity": severity,
        "issues": issues,
        "warnings": unique_warnings,
        "normalized": {
            "project": normalized_project,
            "intelligence": normalized_intelligence,
            "strategy": normalized_strategy,
            "pricing": normalized_pricing,
            "proposal": normalized_proposal,
        },
    }
