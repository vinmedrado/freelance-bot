"""Camada deterministica de entendimento do projeto antes da proposta."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from knowledge_engine import load_knowledge

Complexity = Literal["low", "medium", "high"]


class ProposalIntelligence(TypedDict):
    category: str
    problem_summary: str
    client_goal: str
    complexity: Complexity
    scope_confidence: float
    relevant_services: list[dict[str, Any]]
    relevant_technologies: list[str]
    relevant_cases: list[dict[str, Any]]
    relevant_experience: list[dict[str, Any]]
    deliverables: list[str]
    risks: list[str]
    clarifying_questions: list[str]
    timeline: list[str]
    pricing_context: dict[str, Any]
    commercial_arguments: list[str]


@dataclass(frozen=True)
class CategoryRule:
    name: str
    keywords: tuple[str, ...]
    service_ids: tuple[str, ...] = ()
    deliverables: tuple[str, ...] = ()
    arguments: tuple[str, ...] = ()


@dataclass
class ProjectSignal:
    category: str
    score: int
    hits: list[str] = field(default_factory=list)


CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule("Excel", ("excel", "vba", "macro", "planilha"), ("excel_vba",), ("Planilha automatizada", "Validações e fórmulas", "Documentação de uso"), ("Redução de retrabalho manual", "Facilidade de manutenção")),
    CategoryRule("Power BI", ("power bi", "dax", "power query", "dataflow"), ("power_bi",), ("Dashboard Power BI", "Modelagem de dados", "Indicadores validados"), ("Indicadores confiáveis", "Visão executiva dos dados")),
    CategoryRule("Python", ("python", "pandas", "script"), ("automation_python",), ("Script Python", "Tratamento de erros", "Documentação técnica"), ("Automação sob medida", "Código organizado para evolução")),
    CategoryRule("API", ("api", "rest", "endpoint", "fastapi", "webhook", "integração"), ("api_backend",), ("API REST", "Integração com sistemas", "Documentação técnica"), ("Integração entre sistemas", "Estrutura escalável")),
    CategoryRule("ETL", ("etl", "pipeline", "limpeza", "tratamento", "carga", "transformação"), ("data_engineering",), ("Pipeline de dados", "Validação dos dados", "Logs de execução"), ("Dados mais confiáveis", "Processo auditável")),
    CategoryRule("Dashboard", ("dashboard", "relatório", "indicador", "kpi", "bi"), ("power_bi", "excel_vba"), ("Dashboard", "Indicadores", "Validação visual"), ("Leitura rápida dos resultados", "Apoio à decisão")),
    CategoryRule("Automação", ("automação", "automatizar", "rotina", "processo manual", "e-mail", "whatsapp"), ("automation_python",), ("Automação", "Rotina executável", "Testes de fluxo"), ("Menos operação manual", "Padronização do processo")),
    CategoryRule("Web Scraping", ("scraping", "crawler", "raspagem", "selenium", "playwright", "beautifulsoup", "coleta automatizada"), ("scraping",), ("Coletor automatizado", "Exportação estruturada", "Tratamento de falhas"), ("Coleta recorrente de dados", "Resiliência a falhas")),
    CategoryRule("Desktop", ("desktop", "executável", "offline", "pyqt", "customtkinter", "tkinter"), ("desktop",), ("Aplicação desktop", "Instalador ou executável", "Orientação de uso"), ("Uso local simplificado", "Independência de navegador")),
    CategoryRule("Full Stack", ("full stack", "saas", "frontend", "backend", "react", "sistema web"), ("fullstack", "api_backend"), ("Frontend", "Backend", "Banco de dados", "Deploy"), ("Solução completa", "Base preparada para crescimento")),
    CategoryRule("Machine Learning", ("machine learning", "modelo", "previsão", "classificação", "xgboost", "lightgbm"), (), ("Pipeline de modelagem", "Avaliação do modelo", "Relatório técnico"), ("Decisões baseadas em dados", "Validação antes de produção")),
    CategoryRule("Banco de Dados", ("banco de dados", "sql", "postgresql", "sqlite", "sql server", "database"), ("data_engineering", "api_backend"), ("Modelo de dados", "Consultas SQL", "Validação de persistência"), ("Dados estruturados", "Consultas mais eficientes")),
)

VAGUE_TERMS = ("urgente", "simples", "rápido", "só", "apenas", "melhorar", "ajustar")
INTEGRATION_TERMS = ("api", "integração", "webhook", "oauth", "login", "whatsapp", "e-mail", "outlook", "mercado livre")
SHORT_DEADLINE_TERMS = ("hoje", "amanhã", "24h", "48h", "urgente", "prazo curto")
INCOMPLETE_DATA_TERMS = ("sem dados", "não tenho dados", "dados incompletos", "base incompleta", "a definir")


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _get(project: Any, key: str, default: Any = "") -> Any:
    if isinstance(project, dict):
        return project.get(key, default)
    return getattr(project, key, default)


def _project_text(project: Any) -> str:
    skills = _get(project, "skills", []) or []
    return _normalize(" ".join([_get(project, "title", ""), _get(project, "description", ""), " ".join(map(str, skills))]))


def _contains(haystack: str, phrase: str) -> bool:
    normalized = _normalize(phrase)
    if not normalized:
        return False
    if " " in normalized:
        return normalized in haystack
    return re.search(rf"\b{re.escape(normalized)}\b", haystack) is not None


def _classify(text: str) -> tuple[str, list[ProjectSignal]]:
    signals: list[ProjectSignal] = []
    for rule in CATEGORY_RULES:
        hits = [keyword for keyword in rule.keywords if _contains(text, keyword)]
        if hits:
            signals.append(ProjectSignal(rule.name, len(hits), hits))
    signals.sort(key=lambda item: item.score, reverse=True)
    return (signals[0].category if signals else "", signals)


def _select_technologies(text: str, knowledge: dict[str, dict[str, Any]]) -> list[str]:
    selected: list[str] = []
    for group in knowledge["technologies"].get("tecnologias", {}).values():
        if not isinstance(group, list):
            continue
        for tech in group:
            if _contains(text, str(tech)):
                selected.append(str(tech))
    return list(dict.fromkeys(selected))


def _select_services(signals: list[ProjectSignal], knowledge: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    service_ids: list[str] = []
    for signal in signals:
        rule = next((item for item in CATEGORY_RULES if item.name == signal.category), None)
        if rule:
            service_ids.extend(rule.service_ids)
    services = []
    for service in knowledge["services"].get("servicos", []):
        if service.get("id") in service_ids:
            services.append(service)
    return services[:4]


def _select_cases(text: str, technologies: list[str], knowledge: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    weak_techs = {"python"}
    for case in knowledge["portfolio"].get("projetos", []):
        problem_hits = [
            item
            for item in case.get("usar_quando", [])
            if _normalize(item) not in weak_techs and _contains(text, item)
        ]
        tech_hits = [tech for tech in case.get("tecnologias", []) if tech in technologies and _normalize(tech) not in weak_techs]
        score = len(problem_hits) * 5 + len(tech_hits)
        if score and (problem_hits or tech_hits):
            cases.append({**case, "score": score, "aderencia": list(dict.fromkeys(problem_hits + tech_hits))})
    cases.sort(key=lambda item: item["score"], reverse=True)
    return cases[:2]


def _select_experience(text: str, knowledge: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for experience in knowledge["experience"].get("experiencias", []):
        activities = [activity for activity in experience.get("atividades", []) if any(_contains(_normalize(activity), token) for token in text.split() if len(token) >= 5)]
        if activities:
            selected.append({
                "empresa": experience.get("empresa", ""),
                "projeto_cliente": experience.get("projeto_cliente", ""),
                "cargo": experience.get("cargo", ""),
                "atividades_relacionadas": activities[:3],
            })
    return selected[:3]


def _complexity(text: str, technologies: list[str], signals: list[ProjectSignal]) -> Complexity:
    score = 0
    word_count = len(text.split())
    if word_count > 80:
        score += 2
    elif word_count > 35:
        score += 1
    if len(technologies) >= 5:
        score += 2
    elif len(technologies) >= 3:
        score += 1
    if sum(1 for term in INTEGRATION_TERMS if _contains(text, term)) >= 2:
        score += 2
    if any(_contains(text, term) for term in ("multi tenant", "pagamento", "deploy", "autenticação", "mlops", "tempo real")):
        score += 2
    if len(signals) >= 4:
        score += 1
    if any(signal.category in {"Power BI", "Dashboard", "ETL"} for signal in signals) and len(technologies) >= 3:
        score += 1
    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _risks(text: str, description: str) -> list[str]:
    risks: list[str] = []
    if len(_normalize(description).split()) < 25 or any(_contains(text, term) for term in VAGUE_TERMS):
        risks.append("escopo vago")
    if any(_contains(text, term) for term in INTEGRATION_TERMS):
        risks.append("integrações externas")
    if any(_contains(text, term) for term in SHORT_DEADLINE_TERMS):
        risks.append("prazo curto")
    if any(_contains(text, term) for term in ("depende", "acesso", "credenciais", "cliente envia", "aprovação")):
        risks.append("dependências")
    if any(_contains(text, term) for term in INCOMPLETE_DATA_TERMS):
        risks.append("dados incompletos")
    return list(dict.fromkeys(risks))


def _questions(category: str, risks: list[str]) -> list[str]:
    questions = ["Qual é o resultado final esperado e como ele será validado?"]
    if "escopo vago" in risks:
        questions.append("Quais telas, arquivos, regras ou etapas fazem parte do escopo inicial?")
    if "integrações externas" in risks:
        questions.append("As credenciais, APIs e ambientes de teste já estão disponíveis?")
    if "dados incompletos" in risks:
        questions.append("Qual é a origem dos dados e existe uma amostra real para validação?")
    if category in {"Dashboard", "Power BI", "Excel"}:
        questions.append("Quais indicadores e filtros são obrigatórios na primeira entrega?")
    return list(dict.fromkeys(questions))[:5]


def _summary(project: Any) -> tuple[str, str]:
    title = str(_get(project, "title", "") or "").strip()
    description = str(_get(project, "description", "") or "").strip()
    first_sentence = re.split(r"(?<=[.!?])\s+", description)[0][:220] if description else ""
    problem = first_sentence or title
    goal = f"Resolver {title.lower()} com uma entrega funcional e validada." if title else "Entregar uma solução funcional e validada para o problema informado."
    return problem, goal


def _deliverables_and_arguments(signals: list[ProjectSignal]) -> tuple[list[str], list[str]]:
    deliverables: list[str] = []
    arguments: list[str] = []
    for signal in signals[:3]:
        rule = next((item for item in CATEGORY_RULES if item.name == signal.category), None)
        if rule:
            deliverables.extend(rule.deliverables)
            arguments.extend(rule.arguments)
    deliverables.extend(["Testes de funcionamento", "Documentação objetiva"])
    return list(dict.fromkeys(deliverables))[:8], list(dict.fromkeys(arguments))[:6]


def build_proposal_intelligence(project: Any) -> ProposalIntelligence:
    """Gera contexto estruturado para IA e motor de preço sem calcular proposta."""
    knowledge = load_knowledge()
    text = _project_text(project)
    category, signals = _classify(text)
    technologies = _select_technologies(text, knowledge)
    services = _select_services(signals, knowledge)
    cases = _select_cases(text, technologies, knowledge)
    experience = _select_experience(text, knowledge)
    complexity = _complexity(text, technologies, signals)
    risks = _risks(text, str(_get(project, "description", "") or ""))
    deliverables, arguments = _deliverables_and_arguments(signals)
    problem_summary, client_goal = _summary(project)
    confidence = max(0.25, min(0.95, 0.35 + len(signals) * 0.12 + len(technologies) * 0.04 - len(risks) * 0.06))

    return {
        "category": category,
        "problem_summary": problem_summary,
        "client_goal": client_goal,
        "complexity": complexity,
        "scope_confidence": round(confidence, 2),
        "relevant_services": services,
        "relevant_technologies": technologies,
        "relevant_cases": cases,
        "relevant_experience": experience,
        "deliverables": deliverables,
        "risks": risks,
        "clarifying_questions": _questions(category, risks),
        "timeline": ["Levantamento", "Desenvolvimento", "Testes", "Entrega"],
        "pricing_context": {
            "budget_text": _get(project, "budget_text", "") or "",
            "complexity": complexity,
            "scope_confidence": round(confidence, 2),
            "service_ids": [service.get("id") for service in services],
            "technology_count": len(technologies),
            "risk_count": len(risks),
            "pricing_rules": knowledge.get("pricing", {}),
        },
        "commercial_arguments": arguments,
    }
