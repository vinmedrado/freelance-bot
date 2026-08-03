from __future__ import annotations

import logging
import math
import re
import warnings
from datetime import date
from typing import Any

from fpdf import FPDF

try:
    from fpdf.enums import XPos, YPos
except ImportError:  # pragma: no cover - fpdf classico.
    XPos = None
    YPos = None

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", message='The parameter "ln" is deprecated', category=DeprecationWarning)
warnings.filterwarnings("ignore", message='"dest" parameter is deprecated', category=DeprecationWarning)

INK = (24, 31, 42)
MUTED = (91, 101, 115)
LIGHT = (247, 248, 250)
LINE = (222, 226, 232)
PETROL = (19, 78, 94)
GREEN = (24, 128, 88)
GOLD = (176, 132, 57)
WHITE = (255, 255, 255)

LEFT = 16
RIGHT = 16
CONTENT_W = 210 - LEFT - RIGHT
BOTTOM_Y = 280
PORTFOLIO_URL = "https://vinmedrado.github.io/portfolio/"
GITHUB_URL = "https://github.com/vinmedrado"

STRUCTURED_KEYS = {
    "headline",
    "executive_summary",
    "understanding",
    "identified_challenges",
    "proposed_solution",
    "deliverables",
    "work_method",
    "timeline",
    "technologies",
    "relevant_cases",
    "proof_points",
    "investment_summary",
    "assumptions",
    "clarifying_questions",
    "next_step",
    "proposal_text",
    "short_proposal_text",
}

GENERIC_HEADLINE_PREFIXES = (
    "solucao objetiva para",
    "solução objetiva para",
    "o projeto consiste",
    "desenvolvimento de",
    "proposta para",
)


def sanitize_pdf_text(value: Any) -> str:
    """Normaliza caracteres incompatíveis com Latin-1 preservando acentos."""
    if value is None:
        return ""
    text = str(value)
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "\u2022": "-",
        "\u2713": "OK",
        "\u2192": "->",
        "\u00b7": "-",
        "\u20ac": "EUR",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _cell_next(pdf: FPDF, *args: Any, **kwargs: Any) -> None:
    if XPos is not None and YPos is not None:
        pdf.cell(*args, new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kwargs)
    else:
        pdf.cell(*args, ln=1, **kwargs)


def _get(data: Any, key: str, default: Any = "") -> Any:
    if isinstance(data, dict):
        return data.get(key, default)
    return getattr(data, key, default)


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_text(value: Any) -> str:
    return " ".join(sanitize_pdf_text(value).split())


def _money_value(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _safe_int(value: Any) -> int:
    try:
        number = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _format_currency(value: float) -> str:
    if value <= 0:
        return "Estimativa após validação"
    return f"R$ {value:,.0f}".replace(",", ".")


def _extract_money(text: Any) -> float:
    content = _clean_text(text)
    matches = re.findall(r"R\$\s*([0-9][0-9\.\,]*)", content)
    for raw in matches:
        normalized = raw.replace(".", "").replace(",", ".")
        value = _money_value(normalized)
        if value:
            return value
    return 0.0


def _extract_hours(text: Any) -> int:
    content = _clean_text(text).lower()
    patterns = (
        r"aproximadamente\s+(\d{1,4})\s+horas",
        r"cerca de\s+(\d{1,4})\s+horas",
        r"(\d{1,4})\s+horas",
        r"(\d{1,4})h\b",
    )
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return _safe_int(match.group(1))
    return 0


def _truncate(text: str, limit: int) -> str:
    content = _clean_text(text)
    if len(content) <= limit:
        return content
    cut = content[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;")
    return f"{cut}."


def _first_sentence(value: Any, limit: int = 220) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    for marker in (". ", "? ", "! "):
        pos = text.find(marker)
        if pos > 24:
            return _truncate(text[: pos + 1], limit)
    return _truncate(text, limit)


def _has_structured(data: dict[str, Any]) -> bool:
    return any(key in data and data.get(key) for key in STRUCTURED_KEYS - {"proposal_text", "short_proposal_text"})


def _structured_from_project(project: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("structured_proposal", "proposal", "proposta_estruturada"):
        container = project.get(key)
        if isinstance(container, dict) and _has_structured(container):
            return dict(container)
    if _has_structured(project):
        return {key: project.get(key) for key in STRUCTURED_KEYS if key in project}
    return None


def _override_persisted_pricing(project: dict[str, Any], pricing: dict[str, Any]) -> dict[str, Any]:
    result = dict(pricing)
    if project.get("suggested_price_brl") not in (None, ""):
        result["suggested_price_brl"] = _money_value(project.get("suggested_price_brl"))
    if project.get("estimated_hours") not in (None, ""):
        result["estimated_hours"] = _safe_int(project.get("estimated_hours"))
    return result


def _build_structured_without_ai(project: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from commercial_strategy import build_commercial_strategy
        from knowledge_engine import load_knowledge
        from pricing_engine import calculate_pricing
        from proposal_generator_v2 import generate_proposal
        from proposal_intelligence import build_proposal_intelligence

        knowledge = load_knowledge()
        intelligence = build_proposal_intelligence(project)
        strategy = build_commercial_strategy(project, intelligence, knowledge)
        pricing = _override_persisted_pricing(project, calculate_pricing(project, intelligence, strategy, knowledge))
        proposal = generate_proposal(project, intelligence, strategy, pricing, knowledge)
        return {**proposal, "pricing": pricing, "intelligence": intelligence}
    except Exception as exc:
        logger.exception("Falha ao reconstruir proposta estruturada para PDF; usando fallback legado: %s", exc)
        return None


def _proposal_data(project: dict[str, Any]) -> dict[str, Any]:
    structured = _structured_from_project(project)
    if structured is not None:
        return structured
    rebuilt = _build_structured_without_ai(project)
    if rebuilt is not None:
        return rebuilt
    text = project.get("proposal_text") or "Proposta preparada a partir das informações disponíveis do projeto."
    return {
        "headline": "",
        "executive_summary": _first_sentence(text),
        "understanding": "",
        "identified_challenges": [],
        "proposed_solution": text,
        "deliverables": [],
        "work_method": [],
        "timeline": [],
        "technologies": [],
        "relevant_cases": [],
        "proof_points": [],
        "investment_summary": project.get("ai_reasoning") or "",
        "assumptions": [],
        "clarifying_questions": [],
        "next_step": "Validar os detalhes finais para organizar o início do trabalho.",
        "proposal_text": text,
        "short_proposal_text": _first_sentence(text),
    }


def _dedupe_texts(items: list[Any], max_items: int | None = None) -> list[str]:
    values = [_clean_text(item) for item in items if _clean_text(item)]
    groups: list[tuple[set[str], str]] = []
    synonyms = {
        "dashboard": {"dashboard", "painel"},
        "indicadores": {"indicadores", "indicador"},
        "documentacao": {"documentacao", "documentação"},
        "testes": {"testes", "validacao", "validação"},
        "api": {"api", "rest"},
    }
    for value in values:
        lower = value.lower()
        tokens = set(re.findall(r"[a-zA-ZÀ-ÿ0-9]+", lower))
        keys = {name for name, words in synonyms.items() if tokens & words}
        matched = False
        for idx, (group_keys, current) in enumerate(groups):
            if keys and group_keys and keys & group_keys:
                if len(value) > len(current):
                    groups[idx] = (group_keys | keys, value)
                matched = True
                break
            if lower == current.lower() or lower in current.lower() or current.lower() in lower:
                groups[idx] = (group_keys | keys, value if len(value) > len(current) else current)
                matched = True
                break
        if not matched:
            groups.append((keys, value))
    result = [value for _, value in groups]
    return result[:max_items] if max_items else result


def _fallback_headline(project: dict[str, Any], proposal: dict[str, Any]) -> str:
    category = _clean_text(project.get("category") or _get(proposal.get("intelligence", {}), "category") or "")
    title = _clean_text(project.get("title"))
    objective = _clean_text(_get(proposal.get("intelligence", {}), "client_goal") or proposal.get("understanding"))
    source = title or objective or category or "Projeto sob medida"
    lower = source.lower()
    if "automação" in lower or "automacao" in lower or "python" in lower:
        return "Automação Python para reduzir trabalho manual"
    if "power bi" in lower or "dashboard" in lower:
        return "Dashboard Power BI para análise clara dos indicadores"
    if "excel" in lower or "planilha" in lower:
        return "Planilha funcional para organizar e validar dados"
    if "scraping" in lower or "coleta" in lower:
        return "Automação de coleta de dados com execução confiável"
    if "api" in lower or "integra" in lower:
        return "Integração estruturada entre sistemas e dados"
    if "full stack" in lower or "sistema" in lower or "aplicação" in lower or "aplicacao" in lower:
        return "Aplicação sob medida para organizar o fluxo operacional"
    if "mapa de calor" in lower or "heatmap" in lower or "financeiro" in lower:
        return "Mapa de calor financeiro para análise visual do mercado"
    return _truncate(f"{category} para {source}" if category and category.lower() not in lower else source, 80)


def _resolve_headline(project: dict[str, Any], proposal: dict[str, Any]) -> str:
    raw = _clean_text(proposal.get("headline") or _get(project.get("structured_proposal", {}), "headline"))
    lower = raw.lower()
    title_lower = _clean_text(project.get("title")).lower()
    if ("automação" in title_lower or "automacao" in title_lower or "python" in title_lower) and (
        "planilha" in lower or "excel" in lower
    ):
        return _fallback_headline(project, proposal)
    if raw and len(raw) <= 100 and not any(lower.startswith(prefix) for prefix in GENERIC_HEADLINE_PREFIXES):
        return _truncate(raw, 80)
    return _fallback_headline(project, proposal)


def _resolve_price(project: dict[str, Any], proposal: dict[str, Any]) -> float:
    pricing = project.get("pricing") if isinstance(project.get("pricing"), dict) else {}
    embedded_pricing = proposal.get("pricing") if isinstance(proposal.get("pricing"), dict) else {}
    for value in (
        _get(pricing, "suggested_price_brl"),
        _get(embedded_pricing, "suggested_price_brl"),
        project.get("suggested_price_brl"),
        project.get("valor_sugerido_brl"),
    ):
        number = _money_value(value)
        if number:
            return number
    return _extract_money(proposal.get("investment_summary"))


def _resolve_hours(project: dict[str, Any], proposal: dict[str, Any]) -> int:
    pricing = project.get("pricing") if isinstance(project.get("pricing"), dict) else {}
    embedded_pricing = proposal.get("pricing") if isinstance(proposal.get("pricing"), dict) else {}
    for value in (
        _get(pricing, "estimated_hours"),
        _get(embedded_pricing, "estimated_hours"),
        project.get("estimated_hours"),
        project.get("estimativa_horas"),
    ):
        hours = _safe_int(value)
        if hours:
            return hours
    return _extract_hours(proposal.get("investment_summary"))


def _deadline(hours: int, proposal: dict[str, Any], requires_scope_validation: bool) -> str:
    if requires_scope_validation:
        return "Prazo a confirmar após validação"
    text = _clean_text(proposal.get("timeline_summary") or proposal.get("deadline"))
    if text:
        return text
    if hours <= 0:
        return "A confirmar"
    if hours <= 8:
        return "2 a 4 dias úteis"
    if hours <= 36:
        return "5 a 8 dias úteis"
    if hours <= 90:
        return "2 a 3 semanas"
    return "4 a 8 semanas"


def _solution_text(proposal: dict[str, Any], deliverables: list[str]) -> str:
    raw = _clean_text(proposal.get("proposed_solution"))
    lower = raw.lower()
    generic = not raw or raw.startswith("sair de uma necessidade") or "solução objetiva" in lower
    if not generic:
        return _truncate(raw, 520)
    understanding = _clean_text(proposal.get("understanding"))
    if understanding and deliverables:
        return _truncate(f"A execução parte da validação do contexto e segue para a construção de {', '.join(deliverables[:3]).lower()}, com conferência final e orientação de uso.", 520)
    return _truncate(understanding or proposal.get("proposal_text") or "", 520)


def resolve_pdf_data(project: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Resolve uma fonte única e consistente para renderização do PDF."""
    proposal = _proposal_data(project)
    intelligence = proposal.get("intelligence") if isinstance(proposal.get("intelligence"), dict) else {}
    pricing = project.get("pricing") if isinstance(project.get("pricing"), dict) else proposal.get("pricing", {})
    price = _resolve_price(project, proposal)
    hours = _resolve_hours(project, proposal)
    requires_scope_validation = bool(
        _get(pricing, "requires_scope_validation", False)
        or project.get("requires_scope_validation")
        or ("estimativa inicial" in _clean_text(proposal.get("investment_summary")).lower())
    )
    deliverables = _dedupe_texts(_safe_list(proposal.get("deliverables")), 6)
    summary = _truncate(_clean_text(proposal.get("executive_summary") or proposal.get("proposal_text")), 430)
    deadline = _deadline(hours, proposal, requires_scope_validation)
    category = _clean_text(project.get("category") or _get(intelligence, "category") or "")
    investment_summary = _clean_text(proposal.get("investment_summary"))
    if not price and re.search(r"R\$\s*0(?:[,.]00)?\b", investment_summary):
        investment_summary = "Estimativa após validação dos dados, entregáveis e escopo final."
    if not hours and re.search(r"\b0\s+horas\b", investment_summary.lower()):
        investment_summary = re.sub(r",?\s*considerando aproximadamente\s+0\s+horas de trabalho[^.]*\.", ".", investment_summary, flags=re.IGNORECASE)
        investment_summary = re.sub(r"\b0\s+horas\b", "horas a confirmar", investment_summary, flags=re.IGNORECASE)
    if price and ("R$ 0" in investment_summary or not investment_summary):
        included = "desenvolvimento, validação e ajustes finais"
        investment_summary = f"O investimento sugerido é de {_format_currency(price)}"
        if hours:
            investment_summary += f", considerando aproximadamente {hours} horas de trabalho para {included}."
        else:
            investment_summary += f", incluindo {included}."
    if requires_scope_validation and "estimativa" not in investment_summary.lower():
        investment_summary += " Esta é uma estimativa inicial e pode ser refinada após a validação do escopo."

    return {
        "title": _clean_text(project.get("title") or "Projeto personalizado"),
        "headline": _resolve_headline(project, proposal),
        "summary": summary,
        "platform": _clean_text(project.get("platform") or "Não informada"),
        "category": category or "Projeto",
        "price": price,
        "hours": hours,
        "deadline": deadline,
        "solution": _solution_text(proposal, deliverables),
        "deliverables": deliverables,
        "timeline": [item for item in _safe_list(proposal.get("timeline")) if isinstance(item, dict)][:4],
        "technologies": _dedupe_texts(_safe_list(proposal.get("technologies")), 6),
        "proof_points": _dedupe_texts(_safe_list(proposal.get("proof_points")), 2),
        "cases": [item for item in _safe_list(proposal.get("relevant_cases")) if isinstance(item, dict)][:2],
        "investment_summary": investment_summary,
        "next_step": _clean_text(proposal.get("next_step") or "Validar os detalhes finais para organizar o início do trabalho."),
        "assumptions": _dedupe_texts(_safe_list(proposal.get("assumptions")), 4),
        "requires_scope_validation": requires_scope_validation,
        "profile_name": _clean_text(profile.get("nome") or "Vinicius Medrado"),
        "profile_title": _clean_text(profile.get("titulo") or "Automação de Processos e Engenharia de Dados"),
    }


class ProposalPDF(FPDF):
    def __init__(self, profile: dict[str, Any]) -> None:
        super().__init__(format="A4")
        self.profile = profile
        self.set_margins(LEFT, 16, RIGHT)
        self.set_auto_page_break(False)
        self.alias_nb_pages()
        try:
            self.set_compression(False)
        except AttributeError:
            pass

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(10)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(CONTENT_W / 2, 4, sanitize_pdf_text(self.profile.get("nome", "Vinicius Medrado")))
        self.cell(CONTENT_W / 2, 4, "Proposta comercial", align="R")
        self.set_draw_color(*LINE)
        self.line(LEFT, 17, 210 - RIGHT, 17)
        self.set_y(24)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*LINE)
        self.line(LEFT, self.get_y(), 210 - RIGHT, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "", 7.2)
        self.set_text_color(*MUTED)
        self.cell(CONTENT_W / 2, 4, "Documento preparado para este projeto")
        self.cell(CONTENT_W / 2, 4, sanitize_pdf_text(f"Página {self.page_no()}/{{nb}}"), align="R")


def _text_height(text: Any, width: float, font_size: float = 9.5, line_height: float = 4.8) -> float:
    content = sanitize_pdf_text(text).strip()
    if not content:
        return 0
    avg_char_width = font_size * 0.35
    chars_per_line = max(22, int(width / avg_char_width))
    return max(1, math.ceil(len(content) / chars_per_line)) * line_height


def _ensure_space(pdf: ProposalPDF, required: float) -> None:
    if pdf.get_y() + required <= BOTTOM_Y:
        return
    pdf.add_page()
    pdf.set_y(24)


def _section(pdf: ProposalPDF, title: str, required: float = 18) -> None:
    _ensure_space(pdf, required + 9)
    if pdf.get_y() > 28:
        pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11.2)
    pdf.set_text_color(*INK)
    _cell_next(pdf, 0, 5.2, sanitize_pdf_text(title))
    pdf.set_draw_color(*LINE)
    pdf.line(LEFT, pdf.get_y(), 210 - RIGHT, pdf.get_y())
    pdf.ln(2)


def _paragraph(pdf: ProposalPDF, text: Any, width: float = CONTENT_W, size: float = 9.4, line: float = 4.8) -> None:
    content = sanitize_pdf_text(text).strip()
    if not content:
        return
    _ensure_space(pdf, _text_height(content, width, size, line) + 2)
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(*INK)
    pdf.multi_cell(width, line, content, align="L")
    pdf.ln(1)


def _cover_header(pdf: ProposalPDF, data: dict[str, Any]) -> None:
    pdf.set_y(16)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*PETROL)
    pdf.cell(80, 4, sanitize_pdf_text(data["profile_name"]))
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(CONTENT_W - 80, 4, "Proposta comercial", align="R")
    pdf.ln(7)
    pdf.set_draw_color(*LINE)
    pdf.line(LEFT, pdf.get_y(), 210 - RIGHT, pdf.get_y())
    pdf.ln(9)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*INK)
    pdf.multi_cell(CONTENT_W, 8.4, sanitize_pdf_text(data["headline"]), align="L")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    meta = f"{data['title']}  |  {data['platform']}  |  {data['category']}  |  {date.today().strftime('%d/%m/%Y')}"
    pdf.multi_cell(CONTENT_W, 4.6, sanitize_pdf_text(meta), align="L")
    pdf.ln(4)


def _metrics(pdf: ProposalPDF, data: dict[str, Any]) -> None:
    labels = [
        ("Investimento", _format_currency(data["price"])),
        ("Horas", f"{data['hours']} horas" if data["hours"] else "A confirmar"),
        ("Prazo", data["deadline"]),
        ("Categoria", data["category"]),
    ]
    y = pdf.get_y()
    col_w = CONTENT_W / 4
    pdf.set_draw_color(*LINE)
    pdf.line(LEFT, y, 210 - RIGHT, y)
    for idx, (label, value) in enumerate(labels):
        x = LEFT + idx * col_w
        if idx:
            pdf.line(x, y + 3, x, y + 21)
        pdf.set_xy(x + 3, y + 4)
        pdf.set_font("Helvetica", "", 7.6)
        pdf.set_text_color(*MUTED)
        pdf.cell(col_w - 6, 4, sanitize_pdf_text(label.upper()))
        pdf.set_xy(x + 3, y + 10)
        pdf.set_font("Helvetica", "B", 9.3)
        pdf.set_text_color(*INK)
        pdf.multi_cell(col_w - 6, 4.2, sanitize_pdf_text(value), align="L")
    pdf.set_y(y + 25)
    pdf.line(LEFT, pdf.get_y(), 210 - RIGHT, pdf.get_y())
    pdf.ln(6)


def _bullets(pdf: ProposalPDF, items: list[str], max_items: int = 6) -> None:
    for item in items[:max_items]:
        _ensure_space(pdf, _text_height(item, CONTENT_W - 7, 8.8, 4.4) + 2)
        y = pdf.get_y()
        pdf.set_draw_color(*GREEN)
        pdf.set_line_width(0.35)
        pdf.line(LEFT + 1, y + 2.4, LEFT + 2.5, y + 4)
        pdf.line(LEFT + 2.5, y + 4, LEFT + 5, y + 1.4)
        pdf.set_xy(LEFT + 8, y)
        pdf.set_font("Helvetica", "", 8.8)
        pdf.set_text_color(*INK)
        pdf.multi_cell(CONTENT_W - 8, 4.4, sanitize_pdf_text(item), align="L")
        pdf.ln(.7)


def _timeline(pdf: ProposalPDF, timeline: list[dict[str, Any]]) -> None:
    if not timeline:
        return
    _section(pdf, "Cronograma", 22)
    col_w = CONTENT_W / len(timeline)
    y = pdf.get_y()
    for idx, item in enumerate(timeline):
        x = LEFT + idx * col_w
        pdf.set_font("Helvetica", "B", 7.7)
        pdf.set_text_color(*PETROL)
        pdf.set_xy(x, y)
        pdf.cell(col_w - 3, 4, str(idx + 1))
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*INK)
        pdf.set_xy(x, y + 5)
        pdf.multi_cell(col_w - 4, 4, sanitize_pdf_text(_clean_text(item.get("phase") or item.get("name"))), align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(x, y + 14)
        pdf.multi_cell(col_w - 4, 4, sanitize_pdf_text(_clean_text(item.get("duration") or item.get("description"))), align="L")
    pdf.set_y(y + 25)


def _chips(pdf: ProposalPDF, items: list[str]) -> None:
    if not items:
        return
    x = LEFT
    y = pdf.get_y()
    for item in items[:6]:
        width = min(46, max(20, pdf.get_string_width(sanitize_pdf_text(item)) + 8))
        if x + width > 210 - RIGHT:
            x = LEFT
            y += 8
        pdf.set_fill_color(*LIGHT)
        pdf.set_draw_color(*LINE)
        pdf.rect(x, y, width, 6, style="DF")
        pdf.set_xy(x + 3, y + 1.1)
        pdf.set_font("Helvetica", "", 7.4)
        pdf.set_text_color(*MUTED)
        pdf.cell(width - 6, 3.5, sanitize_pdf_text(item))
        x += width + 3
    pdf.set_y(y + 9)


def _cases(pdf: ProposalPDF, cases: list[dict[str, Any]]) -> None:
    valid = [case for case in cases if case.get("name") or case.get("reason")][:2]
    if not valid:
        return
    _section(pdf, "Projetos relacionados", 18)
    for case in valid:
        name = _clean_text(case.get("name"))
        reason = _truncate(_clean_text(case.get("reason")), 170)
        url = _clean_text(case.get("url"))
        _ensure_space(pdf, 16 + _text_height(reason, CONTENT_W, 8.2, 4.2))
        pdf.set_font("Helvetica", "B", 8.8)
        pdf.set_text_color(*INK)
        _cell_next(pdf, 0, 4.5, sanitize_pdf_text(name))
        if reason:
            pdf.set_font("Helvetica", "", 8.2)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(CONTENT_W, 4.2, sanitize_pdf_text(reason), align="L")
        if url:
            pdf.set_font("Helvetica", "", 7.8)
            pdf.set_text_color(*PETROL)
            try:
                _cell_next(pdf, 0, 4.2, "Ver projeto", link=url)
            except TypeError:
                _cell_next(pdf, 0, 4.2, "Ver projeto")
        pdf.ln(1)


def _signature(pdf: ProposalPDF, data: dict[str, Any], profile: dict[str, Any]) -> None:
    _ensure_space(pdf, 30)
    pdf.ln(4)
    y = pdf.get_y()
    pdf.set_draw_color(*LINE)
    pdf.line(LEFT, y, 210 - RIGHT, y)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 9.4)
    pdf.set_text_color(*INK)
    _cell_next(pdf, 0, 4.8, sanitize_pdf_text(data["profile_name"]))
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*MUTED)
    _cell_next(pdf, 0, 4.4, "Automação de Processos e Engenharia de Dados")
    pdf.set_text_color(*PETROL)
    try:
        pdf.cell(22, 4.4, "Portfólio", link=PORTFOLIO_URL)
        pdf.cell(20, 4.4, "GitHub", link=GITHUB_URL)
    except TypeError:
        pdf.cell(42, 4.4, "Portfolio | GitHub")
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4.4, sanitize_pdf_text(f"Data da proposta: {date.today().strftime('%d/%m/%Y')}"), align="R")


def create_proposal_pdf(project: dict[str, Any], profile: dict[str, Any]) -> bytes:
    data = resolve_pdf_data(project, profile)
    simple_project = 0 < int(data["hours"] or 0) <= 8
    pdf = ProposalPDF(profile)
    pdf.add_page()
    _cover_header(pdf, data)

    if data["summary"]:
        _paragraph(pdf, data["summary"], size=9.6, line=5)
        pdf.ln(2)

    _metrics(pdf, data)

    if data["solution"]:
        _section(pdf, "Solução proposta", 18)
        _paragraph(pdf, data["solution"], size=9.3, line=4.8)

    if data["deliverables"]:
        _section(pdf, "Entregáveis", 22)
        _bullets(pdf, data["deliverables"], 6)

    if data["timeline"] and not simple_project:
        _timeline(pdf, data["timeline"])

    if data["investment_summary"]:
        _section(pdf, "Investimento", 16)
        _paragraph(pdf, data["investment_summary"], size=9.2, line=4.7)
    elif data["price"]:
        _section(pdf, "Investimento", 14)
        text = f"O investimento sugerido é de {_format_currency(data['price'])}."
        if data["hours"]:
            text += f" A estimativa considera aproximadamente {data['hours']} horas de trabalho."
        _paragraph(pdf, text, size=9.2, line=4.7)

    if data["proof_points"] and not simple_project:
        _section(pdf, "Experiência relevante", 16)
        _bullets(pdf, data["proof_points"], 2)

    if data["technologies"] and not simple_project:
        _section(pdf, "Tecnologias", 10)
        _chips(pdf, data["technologies"])

    if not simple_project:
        _cases(pdf, data["cases"])

    if data["assumptions"] and not simple_project and (data["requires_scope_validation"] or pdf.get_y() < 235):
        _section(pdf, "Premissas", 12)
        _bullets(pdf, data["assumptions"], 4)

    if data["next_step"]:
        _section(pdf, "Próximo passo", 12)
        _paragraph(pdf, data["next_step"], size=9.2, line=4.7)

    _signature(pdf, data, profile)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        content = pdf.output(dest="S")
    if isinstance(content, str):
        return content.encode("latin-1")
    return bytes(content)
