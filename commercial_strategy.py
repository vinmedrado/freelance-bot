"""Estrategia comercial deterministica para orientar a geracao da proposta."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, TypedDict


class CommercialStrategy(TypedDict):
    positioning: str
    value_proposition: str
    client_priorities: list[str]
    proposal_angle: str
    proof_points: list[str]
    relevant_cases: list[dict[str, str]]
    relevant_experience: list[str]
    objections: list[str]
    responses_to_objections: list[str]
    recommended_tone: str
    cta: str
    sections_emphasis: list[str]
    claims_to_avoid: list[str]


POSITIONING_BY_CATEGORY = {
    "Excel": "especialista em Excel avancado e automacao de planilhas",
    "Power BI": "analista de dados com experiencia em dashboards e Power BI",
    "Python": "desenvolvedor Python para automacao e processamento de dados",
    "API": "desenvolvedor Python para integracoes e APIs",
    "ETL": "engenheiro de dados para pipelines e tratamento de informacoes",
    "Dashboard": "analista de dados com experiencia em dashboards",
    "Automacao": "especialista em automacao de processos",
    "Web Scraping": "desenvolvedor Python para scraping e coleta automatizada",
    "Desktop": "desenvolvedor Python para aplicacoes desktop",
    "Full Stack": "desenvolvedor full stack para aplicacoes sob medida",
    "Machine Learning": "desenvolvedor de solucoes de dados e machine learning",
    "Banco de Dados": "analista de dados com foco em bancos de dados e SQL",
}

ANGLE_BY_CATEGORY = {
    "Excel": "reducao de retrabalho",
    "Power BI": "clareza para decisao",
    "Python": "rapidez operacional",
    "API": "integracao entre sistemas",
    "ETL": "organizacao e confiabilidade",
    "Dashboard": "clareza para decisao",
    "Automacao": "reducao de retrabalho",
    "Web Scraping": "rapidez operacional",
    "Desktop": "experiencia do usuario",
    "Full Stack": "escalabilidade",
    "Machine Learning": "organizacao e confiabilidade",
    "Banco de Dados": "organizacao e confiabilidade",
}

PRIORITIES_BY_CATEGORY = {
    "Excel": ["facilidade de uso", "reducao de trabalho manual", "manutencao futura"],
    "Power BI": ["confiabilidade dos dados", "clareza dos indicadores", "facilidade de atualizacao"],
    "Python": ["reducao de trabalho manual", "tratamento de erros", "manutencao futura"],
    "API": ["integracao", "documentacao", "seguranca"],
    "ETL": ["confiabilidade dos dados", "validacao", "desempenho"],
    "Dashboard": ["clareza dos indicadores", "confiabilidade dos dados", "facilidade de uso"],
    "Automacao": ["reducao de trabalho manual", "padronizacao", "confiabilidade"],
    "Web Scraping": ["coleta confiavel", "tratamento de falhas", "exportacao estruturada"],
    "Desktop": ["facilidade de uso", "instalacao simples", "uso local"],
    "Full Stack": ["escopo claro", "integracao", "manutencao futura"],
    "Machine Learning": ["validacao tecnica", "confiabilidade dos dados", "criterios de avaliacao"],
    "Banco de Dados": ["organizacao dos dados", "desempenho", "confiabilidade"],
}

RISK_TO_OBJECTION = {
    "escopo vago": "escopo ainda vago",
    "integracoes externas": "risco de integracao",
    "prazo curto": "prazo",
    "dependencias": "necessidade de acesso",
    "dados incompletos": "dados incompletos",
}

OBJECTION_RESPONSES = {
    "preco": "A melhor forma de controlar investimento e separar o essencial das melhorias futuras antes de fechar o escopo.",
    "prazo": "Antes de assumir um prazo fechado, valido as etapas criticas para evitar uma estimativa artificial.",
    "manutencao": "Estruturo a entrega com organizacao e orientacao basica de uso para facilitar ajustes futuros.",
    "necessidade de acesso": "Os acessos e arquivos necessarios podem ser validados no levantamento antes do desenvolvimento.",
    "dados incompletos": "Antes do desenvolvimento, valido a estrutura dos dados para reduzir retrabalho e evitar estimativas irreais.",
    "risco de integracao": "A integracao deve comecar por uma validacao tecnica dos acessos, limites e respostas da API.",
    "escopo ainda vago": "O primeiro passo e transformar a necessidade em um escopo objetivo, com entregaveis e criterios de aceite.",
}


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _get(project: Any, key: str, default: Any = "") -> Any:
    if isinstance(project, dict):
        return project.get(key, default)
    return getattr(project, key, default)


def _contains(haystack: str, phrase: str) -> bool:
    normalized = _normalize(phrase)
    if not normalized:
        return False
    if " " in normalized:
        return normalized in haystack
    return re.search(rf"\b{re.escape(normalized)}\b", haystack) is not None


def _project_text(project: Any) -> str:
    skills = _get(project, "skills", []) or []
    return _normalize(" ".join([_get(project, "title", ""), _get(project, "description", ""), " ".join(map(str, skills))]))


def _unique(values: list[str], limit: int | None = None) -> list[str]:
    cleaned = [item for item in dict.fromkeys(value.strip() for value in values if value and value.strip())]
    return cleaned[:limit] if limit else cleaned


def _category(intelligence: dict[str, Any]) -> str:
    return str(intelligence.get("category") or "")


def _lookup_category(mapping: dict[str, Any], category: str, default: Any) -> Any:
    category_key = _normalize(category)
    for key, value in mapping.items():
        if _normalize(key) == category_key:
            return value
    return default


def _positioning(category: str) -> str:
    return _lookup_category(POSITIONING_BY_CATEGORY, category, "consultor tecnico para solucoes de dados e automacao")


def _value_proposition(category: str, intelligence: dict[str, Any]) -> str:
    goal = str(intelligence.get("client_goal") or intelligence.get("problem_summary") or "o problema informado").rstrip(".")
    category_key = _normalize(category)
    if category_key in {"power bi", "dashboard"}:
        return "Organizar os dados e transformar os indicadores em uma visao clara, confiavel e facil de atualizar."
    if category_key in {"automacao", "python", "web scraping"}:
        return "Transformar o processo manual em uma rotina automatizada, validada e mais simples de manter."
    if category_key in {"api", "etl", "banco de dados"}:
        return "Estruturar o fluxo de dados com validacao, integracao e base tecnica preparada para evolucao."
    if category_key == "full stack":
        return "Construir uma aplicacao sob medida com frontend, backend e dados organizados em um fluxo consistente."
    return f"Entregar uma solucao objetiva para {goal}, com escopo validado e foco no uso real."


def _priorities(category: str, intelligence: dict[str, Any]) -> list[str]:
    priorities = list(_lookup_category(PRIORITIES_BY_CATEGORY, category, ["clareza", "confiabilidade", "manutencao futura"]))
    risks = [_normalize(risk) for risk in intelligence.get("risks", []) if isinstance(risk, str)]
    if "prazo curto" in risks:
        priorities.append("prazo")
    if "escopo vago" in risks:
        priorities.append("escopo claro")
    if "dados incompletos" in risks:
        priorities.append("validacao dos dados")
    if any("integr" in risk for risk in risks):
        priorities.append("integracao")
    return _unique(priorities, 5)


def _proposal_angle(category: str, intelligence: dict[str, Any], project_text: str) -> str:
    risks = [_normalize(risk) for risk in intelligence.get("risks", []) if isinstance(risk, str)]
    if "dados incompletos" in risks:
        return "organizacao e confiabilidade"
    if any(_contains(project_text, term) for term in ("automacao", "automatizar", "processo manual", "rotina manual")):
        return "reducao de retrabalho"
    return _lookup_category(ANGLE_BY_CATEGORY, category, "organizacao e confiabilidade")


def _related_score(text: str, value: str) -> int:
    words = [word for word in _normalize(value).split() if len(word) >= 5]
    return sum(1 for word in set(words) if _contains(text, word))


def _proof_points(project_text: str, intelligence: dict[str, Any], knowledge: dict[str, dict[str, Any]]) -> list[str]:
    points: list[str] = []
    for result in knowledge.get("experience", {}).get("resultados_comprovados", []):
        label = f"{result.get('descricao', '')} - {result.get('contexto', '')}"
        if _related_score(project_text, label) > 0:
            points.append(label)

    for experience in intelligence.get("relevant_experience", []):
        if not isinstance(experience, dict):
            continue
        activities = experience.get("atividades_relacionadas", [])
        if activities:
            company = experience.get("empresa", "")
            points.append(f"Experiencia em {activities[0]}{f' ({company})' if company else ''}")

    for case in intelligence.get("relevant_cases", []):
        if isinstance(case, dict) and case.get("nome"):
            points.append(f"Case {case.get('nome')}: {case.get('resumo', '').strip()}")

    return _unique(points, 3)


def _case_reason(case: dict[str, Any], category: str, intelligence: dict[str, Any]) -> str:
    adherence = [str(item) for item in case.get("aderencia", []) if item]
    if adherence:
        return f"Relacionado ao projeto por envolver {', '.join(adherence[:3])}, pontos centrais para {category or 'esta entrega'}."
    summary = str(intelligence.get("problem_summary") or "o problema do cliente")
    return f"Relacionado por tratar de um desafio semelhante ao escopo: {summary[:120]}."


def _relevant_cases(category: str, intelligence: dict[str, Any]) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for case in intelligence.get("relevant_cases", [])[:2]:
        if not isinstance(case, dict):
            continue
        cases.append({
            "name": str(case.get("nome", "")),
            "reason": _case_reason(case, category, intelligence),
            "url": str(case.get("demonstracao") or ""),
        })
    return cases


def _relevant_experience(project_text: str, intelligence: dict[str, Any], knowledge: dict[str, dict[str, Any]]) -> list[str]:
    selected: list[str] = []
    for item in intelligence.get("relevant_experience", []):
        if isinstance(item, dict):
            selected.extend(str(activity) for activity in item.get("atividades_relacionadas", []) if activity)

    if len(selected) < 3:
        for experience in knowledge.get("experience", {}).get("experiencias", []):
            for activity in experience.get("atividades", []):
                if _related_score(project_text, activity) > 0:
                    selected.append(str(activity))
    return _unique(selected, 5)


def _objections(intelligence: dict[str, Any]) -> list[str]:
    objections: list[str] = []
    for risk in intelligence.get("risks", []):
        normalized = _normalize(risk)
        objections.append(RISK_TO_OBJECTION.get(normalized, str(risk)))
    if intelligence.get("complexity") == "high":
        objections.append("prazo")
    if not objections:
        objections.append("manutencao")
    return _unique(objections, 3)


def _responses(objections: list[str]) -> list[str]:
    return [OBJECTION_RESPONSES.get(_normalize(objection), "O ponto deve ser alinhado de forma objetiva antes do inicio.") for objection in objections]


def _tone(category: str, intelligence: dict[str, Any]) -> str:
    category_key = _normalize(category)
    if category_key in {"power bi", "dashboard"}:
        return "consultivo e executivo"
    if category_key in {"api", "etl", "full stack", "machine learning"}:
        return "consultivo e tecnico"
    if "escopo vago" in intelligence.get("risks", []):
        return "consultivo e direto"
    return "consultivo e direto"


def _cta(category: str, intelligence: dict[str, Any]) -> str:
    risks = [_normalize(risk) for risk in intelligence.get("risks", []) if isinstance(risk, str)]
    category_key = _normalize(category)
    if category_key in {"automacao", "python", "web scraping", "excel"} and "automacao" in _normalize(" ".join(intelligence.get("deliverables", []))):
        return "validar o processo atual e receber os arquivos de exemplo"
    if "escopo vago" in risks:
        return "validar o escopo inicial e definir os entregaveis essenciais"
    if category_key in {"power bi", "dashboard"}:
        return "alinhar os indicadores e receber uma amostra dos dados"
    if category_key in {"automacao", "python", "web scraping", "excel"}:
        return "validar o processo atual e receber os arquivos de exemplo"
    if category_key in {"api", "etl", "full stack"}:
        return "confirmar as integracoes, acessos e regras principais"
    return "iniciar um levantamento rapido dos requisitos"


def _sections(category: str, intelligence: dict[str, Any]) -> list[str]:
    category_key = _normalize(category)
    sections = ["desafios_identificados", "solucao_proposta", "entregaveis"]
    if intelligence.get("relevant_cases"):
        sections.append("cases")
    if intelligence.get("relevant_experience"):
        sections.append("experiencia")
    if intelligence.get("risks"):
        sections.append("riscos")
    if category_key in {"full stack", "api", "etl"}:
        sections.append("cronograma")
    return _unique(sections, 5)


def _claims_to_avoid(knowledge: dict[str, dict[str, Any]]) -> list[str]:
    avoid = [
        "garantia de resultado",
        "sem qualquer risco",
        "melhor profissional",
        "experiencia especifica nao comprovada",
        "prazo definitivo sem escopo validado",
    ]
    avoid.extend(str(item) for item in knowledge.get("writing_style", {}).get("evitar", [])[:3])
    avoid.extend(str(item) for item in knowledge.get("negotiation", {}).get("nao_incluido_por_padrao", [])[:2])
    return _unique(avoid, 10)


def build_commercial_strategy(
    project: Any,
    intelligence: dict[str, Any],
    knowledge: dict[str, dict[str, Any]],
) -> CommercialStrategy:
    """Transforma a inteligencia tecnica em direcao comercial para a IA."""
    category = _category(intelligence)
    text = _project_text(project)
    objections = _objections(intelligence)

    return {
        "positioning": _positioning(category),
        "value_proposition": _value_proposition(category, intelligence),
        "client_priorities": _priorities(category, intelligence),
        "proposal_angle": _proposal_angle(category, intelligence, text),
        "proof_points": _proof_points(text, intelligence, knowledge),
        "relevant_cases": _relevant_cases(category, intelligence),
        "relevant_experience": _relevant_experience(text, intelligence, knowledge),
        "objections": objections,
        "responses_to_objections": _responses(objections),
        "recommended_tone": _tone(category, intelligence),
        "cta": _cta(category, intelligence),
        "sections_emphasis": _sections(category, intelligence),
        "claims_to_avoid": _claims_to_avoid(knowledge),
    }
