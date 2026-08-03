"""Motor deterministico de precificacao para propostas freelance."""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal, TypedDict

Complexity = Literal["low", "medium", "high"]


class PricingAdjustment(TypedDict):
    factor: str
    multiplier: float
    reason: str


class PricingResult(TypedDict):
    project_type: str
    complexity: Complexity
    estimated_hours: int
    hourly_rate_brl: float
    base_price_brl: float
    adjustments: list[PricingAdjustment]
    suggested_price_brl: float
    minimum_price_brl: float
    maximum_price_brl: float
    confidence: float
    pricing_reason: str
    assumptions: list[str]
    requires_scope_validation: bool


HOUR_RANGES: dict[str, dict[Complexity, tuple[int, int]]] = {
    "ajuste_excel": {"low": (3, 6), "medium": (6, 14), "high": (14, 28)},
    "planilha_automatizada": {"low": (6, 12), "medium": (12, 28), "high": (28, 60)},
    "dashboard_power_bi": {"low": (10, 18), "medium": (18, 36), "high": (36, 80)},
    "automacao_python": {"low": (6, 16), "medium": (16, 40), "high": (40, 90)},
    "scraping": {"low": (10, 20), "medium": (20, 45), "high": (45, 100)},
    "api_backend": {"low": (18, 35), "medium": (35, 80), "high": (80, 180)},
    "aplicacao_fullstack": {"low": (35, 70), "medium": (70, 160), "high": (160, 280)},
    "aplicacao_desktop": {"low": (20, 45), "medium": (45, 100), "high": (100, 220)},
}

COMBINED_MULTIPLIER_CAPS: dict[Complexity, Decimal] = {
    "low": Decimal("1.15"),
    "medium": Decimal("1.35"),
    "high": Decimal("1.60"),
}

TYPE_BY_SERVICE = {
    "power_bi": "dashboard_power_bi",
    "excel_vba": "planilha_automatizada",
    "automation_python": "automacao_python",
    "scraping": "scraping",
    "api_backend": "api_backend",
    "fullstack": "aplicacao_fullstack",
    "desktop": "aplicacao_desktop",
    "data_engineering": "automacao_python",
}

TYPE_BY_CATEGORY = {
    "excel": "ajuste_excel",
    "power bi": "dashboard_power_bi",
    "dashboard": "dashboard_power_bi",
    "python": "automacao_python",
    "automacao": "automacao_python",
    "web scraping": "scraping",
    "api": "api_backend",
    "etl": "automacao_python",
    "full stack": "aplicacao_fullstack",
    "desktop": "aplicacao_desktop",
    "banco de dados": "api_backend",
}

FEATURE_FACTORS = {
    "integration": ("api", "integracao", "webhook", "oauth", "whatsapp", "e mail", "outlook"),
    "authentication": ("autenticacao", "login", "oauth", "permissao", "usuario"),
    "deployment": ("deploy", "docker", "servidor", "hospedagem", "producao"),
    "frontend": ("frontend", "react", "tela", "interface"),
    "backend": ("backend", "fastapi", "api", "endpoint"),
    "database": ("banco de dados", "postgresql", "sqlite", "sql server", "database"),
    "documentation": ("documentacao", "manual", "orientacao"),
    "urgency": ("urgente", "hoje", "amanha", "24h", "48h", "prazo curto"),
}


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _get(project: Any, key: str, default: Any = "") -> Any:
    if isinstance(project, dict):
        return project.get(key, default)
    return getattr(project, key, default)


def _text(project: Any) -> str:
    skills = _get(project, "skills", []) or []
    return _normalize(" ".join([_get(project, "title", ""), _get(project, "description", ""), " ".join(map(str, skills))]))


def _contains(text: str, phrase: str) -> bool:
    phrase_norm = _normalize(phrase)
    if not phrase_norm:
        return False
    if " " in phrase_norm:
        return phrase_norm in text
    return re.search(rf"\b{re.escape(phrase_norm)}\b", text) is not None


def _money(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _complexity(value: Any) -> Complexity:
    normalized = _normalize(value)
    if normalized in {"low", "baixa", "baixo"}:
        return "low"
    if normalized in {"high", "alta", "alto"}:
        return "high"
    return "medium"


def _pricing_config(knowledge: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return knowledge.get("pricing", {})


def _project_type(project: Any, intelligence: dict[str, Any]) -> str:
    text = _text(project)
    services = intelligence.get("relevant_services", [])
    service_ids = [str(service.get("id", "")) for service in services if isinstance(service, dict)]
    if "fullstack" in service_ids:
        return "aplicacao_fullstack"
    if "api_backend" in service_ids and any(_contains(text, term) for term in ("frontend", "react", "saas", "sistema web")):
        return "aplicacao_fullstack"
    for service_id in service_ids:
        mapped = TYPE_BY_SERVICE.get(service_id)
        if mapped:
            if mapped == "planilha_automatizada" and not any(_contains(text, term) for term in ("automacao", "automatizar", "macro", "vba")):
                return "ajuste_excel"
            return mapped
    category = _normalize(intelligence.get("category", ""))
    mapped = TYPE_BY_CATEGORY.get(category)
    if mapped:
        return mapped
    return "automacao_python"


def _features(text: str) -> set[str]:
    return {name for name, terms in FEATURE_FACTORS.items() if any(_contains(text, term) for term in terms)}


def _scope_is_uncertain(project_text: str, risks: list[str], intelligence: dict[str, Any]) -> bool:
    risk_text = " ".join(_normalize(risk) for risk in risks)
    if "escopo vago" not in risk_text:
        return False
    word_count = len(project_text.split())
    vague_markers = ("coisa", "algo", "simples urgente", "rapido demais", "apenas ajustar")
    if word_count < 12 or any(_contains(project_text, marker) for marker in vague_markers):
        return True
    if len(intelligence.get("deliverables", [])) < 3:
        return True
    return False


def _hour_position(complexity: Complexity, feature_count: int, risk_count: int, deliverable_count: int, scope_confidence: float) -> Decimal:
    base = {"low": Decimal("0.30"), "medium": Decimal("0.42"), "high": Decimal("0.56")}[complexity]
    base += Decimal(min(feature_count, 4)) * Decimal("0.025")
    base += Decimal(min(risk_count, 3)) * Decimal("0.02")
    base += Decimal(max(0, deliverable_count - 3)) * Decimal("0.015")
    if scope_confidence < 0.5:
        base += Decimal("0.06")
    return max(Decimal("0.18"), min(base, Decimal("0.82")))


def _estimated_hours(project_type: str, complexity: Complexity, features: set[str], intelligence: dict[str, Any]) -> int:
    low, high = HOUR_RANGES[project_type][complexity]
    position = _hour_position(
        complexity,
        len(features),
        len(intelligence.get("risks", [])),
        len(intelligence.get("deliverables", [])),
        float(intelligence.get("scope_confidence", 0.6) or 0.6),
    )
    hours = Decimal(low) + (Decimal(high - low) * position)
    return int(hours.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _rate(complexity: Complexity, risks: list[str], features: set[str], pricing: dict[str, Any]) -> Decimal:
    value_hour = pricing.get("valor_hora", {})
    minimum = _money(value_hour.get("minimo"), Decimal("50"))
    target = _money(value_hour.get("alvo"), Decimal("85"))
    maximum = _money(value_hour.get("maximo"), Decimal("150"))
    if complexity == "low":
        rate = minimum + (target - minimum) * Decimal("0.45")
    elif complexity == "high":
        rate = target + (maximum - target) * Decimal("0.35")
    else:
        rate = target - Decimal("2")
    risk_count = len(risks)
    if risk_count >= 3:
        rate += Decimal("10")
    elif risk_count >= 1:
        rate += Decimal("5")
    if "urgency" in features:
        rate += Decimal("12")
    if "authentication" in features or "deployment" in features:
        rate += Decimal("5")
    return max(minimum, min(rate, maximum)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _yaml_multiplier(pricing: dict[str, Any], group: str, key: str, default: str) -> Decimal:
    return _money(pricing.get("multiplicadores", {}).get(group, {}).get(key), Decimal(default))


def _adjustments(
    complexity: Complexity,
    risks: list[str],
    features: set[str],
    pricing: dict[str, Any],
    scope_uncertain: bool,
) -> list[PricingAdjustment]:
    adjustments: list[PricingAdjustment] = []
    complexity_key = {"low": "baixa", "medium": "media", "high": "alta"}[complexity]
    complexity_multiplier = _yaml_multiplier(pricing, "complexidade", complexity_key, "1.0")
    if complexity == "high" and complexity_multiplier != Decimal("1.0"):
        adjustments.append({"factor": "complexity", "multiplier": float(complexity_multiplier), "reason": f"Complexidade {complexity} do escopo."})
    if "urgency" in features:
        adjustments.append({"factor": "urgency", "multiplier": float(_yaml_multiplier(pricing, "urgencia", "ate_7_dias", "1.2")), "reason": "Prazo curto ou urgencia informada."})
    risk_text = " ".join(_normalize(risk) for risk in risks)
    generic_risks = [
        risk
        for risk in risks
        if not (
            ("integr" in _normalize(risk) and "integration" in features)
            or ("dependencias" in _normalize(risk) and "integration" in features)
            or ("dados incompletos" in _normalize(risk))
            or ("escopo vago" in _normalize(risk))
        )
    ]
    generic_risk_count = len(generic_risks)
    risk_level = "alto" if generic_risk_count >= 3 else "medio" if generic_risk_count else "baixo"
    risk_multiplier = _yaml_multiplier(pricing, "risco", risk_level, "1.0")
    if risk_multiplier != Decimal("1.0"):
        adjustments.append({"factor": "risk", "multiplier": float(risk_multiplier), "reason": "Riscos identificados no escopo."})
    factor_reasons = {
        "integration": "Integracao externa exige validacao de acesso e respostas.",
        "authentication": "Autenticacao adiciona regras de seguranca e testes.",
        "data_quality": "Dados incompletos exigem validacao previa.",
        "deployment": "Deploy adiciona preparacao de ambiente.",
        "documentation": "Documentacao e orientacao de uso inclusas.",
        "scope_uncertainty": "Escopo vago exige margem para levantamento.",
        "external_dependency": "Dependencias externas podem afetar execucao.",
    }
    feature_multipliers = {
        "integration": Decimal("1.08"),
        "authentication": Decimal("1.06"),
        "deployment": Decimal("1.05"),
        "documentation": Decimal("1.04"),
    }
    for factor, multiplier in feature_multipliers.items():
        if factor in features:
            adjustments.append({"factor": factor, "multiplier": float(multiplier), "reason": factor_reasons[factor]})
    if "dados incompletos" in risk_text:
        adjustments.append({"factor": "data_quality", "multiplier": 1.06, "reason": factor_reasons["data_quality"]})
    if scope_uncertain:
        adjustments.append({"factor": "scope_uncertainty", "multiplier": 1.07, "reason": factor_reasons["scope_uncertainty"]})
    if "dependencias" in risk_text and "integration" not in features:
        adjustments.append({"factor": "external_dependency", "multiplier": 1.06, "reason": factor_reasons["external_dependency"]})
    seen: set[str] = set()
    unique: list[PricingAdjustment] = []
    for adjustment in adjustments:
        if adjustment["factor"] not in seen:
            unique.append(adjustment)
            seen.add(adjustment["factor"])
    capped: list[PricingAdjustment] = []
    current = Decimal("1.0")
    cap = COMBINED_MULTIPLIER_CAPS[complexity]
    for adjustment in unique:
        multiplier = Decimal(str(adjustment["multiplier"]))
        if current * multiplier > cap:
            multiplier = (cap / current).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if multiplier <= Decimal("1.0"):
                continue
            adjustment = {**adjustment, "multiplier": float(multiplier)}
        capped.append(adjustment)
        current *= multiplier
    return capped


def _combined_multiplier(adjustments: list[PricingAdjustment], complexity: Complexity) -> Decimal:
    combined = Decimal("1.0")
    for adjustment in adjustments:
        combined *= Decimal(str(adjustment["multiplier"]))
    return min(combined, COMBINED_MULTIPLIER_CAPS[complexity])


def _round_money(value: Decimal) -> Decimal:
    if value < Decimal("1000"):
        step = Decimal("50")
    elif value <= Decimal("5000"):
        step = Decimal("100")
    else:
        step = Decimal("250")
    return (value / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


def _range_limits(project_type: str, pricing: dict[str, Any]) -> tuple[Decimal, Decimal]:
    ranges = pricing.get("faixas_por_tipo", {})
    type_range = ranges.get(project_type) or ranges.get("automacao_python", {})
    return _money(type_range.get("minimo"), Decimal("700")), _money(type_range.get("maximo"), Decimal("5000"))


def _budget_numbers(budget_text: str) -> list[Decimal]:
    if not budget_text or any(term in _normalize(budget_text) for term in ("combinar", "negociar", "nao informado")):
        return []
    numbers: list[Decimal] = []
    for raw in re.findall(r"\d[\d\.\,]*", budget_text):
        cleaned = raw.replace(".", "").replace(",", ".")
        try:
            numbers.append(Decimal(cleaned))
        except Exception:
            continue
    return numbers


def _confidence(
    project: Any,
    intelligence: dict[str, Any],
    features: set[str],
    budget_numbers: list[Decimal],
    scope_uncertain: bool,
) -> float:
    text_words = len(_text(project).split())
    score = Decimal(str(float(intelligence.get("scope_confidence", 0.6) or 0.6)))
    if text_words >= 45:
        score += Decimal("0.14")
    elif text_words >= 22:
        score += Decimal("0.10")
    elif text_words < 12:
        score -= Decimal("0.16")
    if intelligence.get("deliverables"):
        score += Decimal("0.08")
    risk_text = " ".join(_normalize(risk) for risk in intelligence.get("risks", []) if risk)
    if "escopo vago" in risk_text and not scope_uncertain:
        score += Decimal("0.27")
    distinct_penalties = 0
    for risk_key in ("dados incompletos", "prazo curto", "dependencias"):
        if risk_key in risk_text:
            distinct_penalties += 1
    if scope_uncertain:
        distinct_penalties += 1
    score -= Decimal(distinct_penalties) * Decimal("0.05")
    if "integration" in features and "authentication" not in features and "api" not in _text(project):
        score -= Decimal("0.04")
    if budget_numbers:
        score += Decimal("0.03")
    return float(max(Decimal("0.20"), min(score, Decimal("0.95"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _requires_validation(
    confidence: float,
    risks: list[str],
    features: set[str],
    complexity: Complexity,
    budget_numbers: list[Decimal],
    minimum: Decimal,
    maximum: Decimal,
    suggested: Decimal,
    scope_uncertain: bool,
) -> bool:
    risk_text = " ".join(_normalize(risk) for risk in risks)
    if scope_uncertain or "dados incompletos" in risk_text or confidence < 0.62:
        return True
    if "integration" in features and "dependencias" in risk_text:
        return True
    if "authentication" in features and scope_uncertain:
        return True
    if complexity == "high" and scope_uncertain:
        return True
    if budget_numbers and max(budget_numbers) < minimum * Decimal("0.75"):
        return True
    return False


def _assumptions(
    project_type: str,
    risks: list[str],
    features: set[str],
    budget_numbers: list[Decimal],
    minimum: Decimal,
    scope_uncertain: bool,
) -> list[str]:
    assumptions = [
        "Inclui desenvolvimento do escopo acordado, validacao funcional e uma rodada de ajustes.",
        "Nao inclui licencas, infraestrutura paga ou manutencao continua.",
    ]
    if project_type in {"dashboard_power_bi", "ajuste_excel", "planilha_automatizada"}:
        assumptions.append("Os dados serao fornecidos em formato estruturado ou em amostra representativa.")
    if "integration" in features:
        assumptions.append("Integracoes externas dependem de acesso valido e documentacao disponivel.")
    if "deployment" in features:
        assumptions.append("Custos de hospedagem ou servicos externos ficam fora do valor de desenvolvimento.")
    if scope_uncertain:
        assumptions.append("O valor considera validacao inicial do escopo antes de fechar prazo definitivo.")
    if budget_numbers and max(budget_numbers) < minimum * Decimal("0.75"):
        assumptions.append("O orcamento informado parece inferior ao minimo comercial para este tipo de entrega.")
    return list(dict.fromkeys(assumptions))[:6]


def _reason(project_type: str, hours: int, intelligence: dict[str, Any], requires_validation: bool) -> str:
    deliverables = [_normalize(item) for item in intelligence.get("deliverables", [])]
    if project_type == "dashboard_power_bi":
        scope = "modelagem dos dados, construcao do dashboard, validacao dos indicadores e ajustes finais"
    elif project_type in {"automacao_python", "scraping"}:
        scope = "mapeamento do processo, automacao, tratamento de falhas, testes e orientacao de uso"
    elif project_type == "aplicacao_fullstack":
        scope = "frontend, backend, banco de dados, integracoes, testes e organizacao da entrega"
    elif any("documentacao" in item for item in deliverables):
        scope = "desenvolvimento, documentacao, testes e uma rodada de ajustes"
    else:
        scope = "desenvolvimento do escopo, validacao funcional e uma rodada de ajustes"
    reason = f"Estimativa baseada em {hours} horas de trabalho, incluindo {scope}."
    if requires_validation:
        reason += " Como ha pontos de escopo a confirmar, a validacao inicial deve ajustar a faixa antes do fechamento."
    return reason


def calculate_pricing(
    project: Any,
    intelligence: dict[str, Any],
    strategy: dict[str, Any],
    knowledge: dict[str, dict[str, Any]],
) -> PricingResult:
    """Calcula preco fechado sugerido sem depender da IA."""
    pricing = _pricing_config(knowledge)
    text = _text(project)
    project_type = _project_type(project, intelligence)
    complexity = _complexity(intelligence.get("complexity", "medium"))
    features = _features(text)
    risks = [str(risk) for risk in intelligence.get("risks", []) if risk]
    scope_uncertain = _scope_is_uncertain(text, risks, intelligence)
    hours = _estimated_hours(project_type, complexity, features, intelligence)
    hourly_rate = _rate(complexity, risks, features, pricing)
    base_price = (Decimal(hours) * hourly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    adjustments = _adjustments(complexity, risks, features, pricing, scope_uncertain)

    combined_multiplier = _combined_multiplier(adjustments, complexity)
    adjusted_price = _round_money(base_price * combined_multiplier)

    configured_minimum, configured_maximum = _range_limits(project_type, pricing)
    suggested = _round_money(max(configured_minimum, adjusted_price))

    over_configured_range = suggested > configured_maximum
    if over_configured_range:
        suggested = _round_money(configured_maximum * Decimal("0.90"))
    minimum_price = _round_money(max(configured_minimum, suggested * Decimal("0.82")))
    if minimum_price >= suggested:
        minimum_price = max(configured_minimum, suggested - (Decimal("50") if suggested < Decimal("1000") else Decimal("100")))
    maximum_price = _round_money(min(configured_maximum, max(suggested * Decimal("1.22"), suggested + Decimal("100"))))
    if maximum_price <= suggested and suggested < configured_maximum:
        maximum_price = min(configured_maximum, suggested + (Decimal("100") if suggested < Decimal("5000") else Decimal("250")))
    if suggested >= configured_maximum:
        maximum_price = configured_maximum
        minimum_price = min(minimum_price, _round_money(max(configured_minimum, suggested * Decimal("0.90"))))

    budget_numbers = _budget_numbers(str(_get(project, "budget_text", "") or ""))
    confidence = _confidence(project, intelligence, features, budget_numbers, scope_uncertain)
    requires_validation = _requires_validation(
        confidence,
        risks,
        features,
        complexity,
        budget_numbers,
        configured_minimum,
        configured_maximum,
        suggested,
        scope_uncertain,
    )
    if over_configured_range:
        requires_validation = True
    assumptions = _assumptions(project_type, risks, features, budget_numbers, configured_minimum, scope_uncertain)
    reason = _reason(project_type, hours, intelligence, requires_validation)
    if over_configured_range:
        reason += " A estimativa tecnica encosta no limite configurado para esse tipo de projeto."
    if budget_numbers and max(budget_numbers) < configured_minimum * Decimal("0.75"):
        reason += " O orcamento informado parece incompativel com o minimo recomendado."

    return {
        "project_type": project_type,
        "complexity": complexity,
        "estimated_hours": hours,
        "hourly_rate_brl": float(hourly_rate),
        "base_price_brl": float(base_price),
        "adjustments": adjustments,
        "suggested_price_brl": float(suggested),
        "minimum_price_brl": float(minimum_price),
        "maximum_price_brl": float(maximum_price),
        "confidence": confidence,
        "pricing_reason": reason,
        "assumptions": assumptions,
        "requires_scope_validation": requires_validation,
    }
