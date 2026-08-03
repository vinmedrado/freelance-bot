"""Gerador estruturado de propostas comerciais para PDF e plataformas."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Protocol, TypedDict


class ProposalV2(TypedDict):
    headline: str
    executive_summary: str
    understanding: str
    identified_challenges: list[str]
    proposed_solution: str
    deliverables: list[str]
    work_method: list[dict[str, str]]
    timeline: list[dict[str, str]]
    technologies: list[str]
    relevant_cases: list[dict[str, str]]
    proof_points: list[str]
    investment_summary: str
    assumptions: list[str]
    clarifying_questions: list[str]
    next_step: str
    proposal_text: str
    short_proposal_text: str


class ProposalRefiner(Protocol):
    def refine_proposal(self, proposal: ProposalV2, constraints: dict[str, Any]) -> dict[str, str]:
        """Retorna textos refinados sem alterar fatos estruturados."""


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


def _contains(text: str, phrase: str) -> bool:
    normalized = _normalize(phrase)
    if not normalized:
        return False
    if " " in normalized:
        return normalized in text
    return re.search(rf"\b{re.escape(normalized)}\b", text) is not None


def _unique(values: list[str], limit: int | None = None) -> list[str]:
    cleaned = [value.strip() for value in dict.fromkeys(values) if value and value.strip()]
    return cleaned[:limit] if limit else cleaned


def _semantic_key(value: str) -> str:
    normalized = _normalize(value)
    groups = {
        "dashboard": ("dashboard power bi", "dashboard", "painel"),
        "indicadores": ("indicadores validados", "indicadores", "kpi"),
        "documentacao": ("documentacao basica", "documentacao objetiva", "documentacao de uso", "documentacao"),
        "testes": ("testes de funcionamento", "validacao funcional", "validacao visual", "testes de fluxo", "testes"),
        "api": ("api rest", "api"),
        "modelo_dados": ("modelo de dados organizado", "modelagem de dados", "modelo de dados"),
        "ajustes": ("uma rodada de ajustes", "rodada de ajustes", "ajustes"),
        "orientacao": ("orientacao basica de uso", "orientacao de uso", "orientacao"),
        "backend": ("backend api", "backend", "api backend"),
        "frontend": ("interface funcional", "frontend", "interface"),
    }
    for key, aliases in groups.items():
        if any(alias in normalized for alias in aliases):
            return key
    return normalized


def _specificity(value: str) -> tuple[int, int]:
    normalized = _normalize(value)
    bonus_terms = ("power bi", "validado", "organizado", "dax", "rest", "funcional", "basica", "necessarias")
    return (sum(1 for term in bonus_terms if term in normalized), len(normalized))


def _semantic_unique(values: list[str], limit: int | None = None) -> list[str]:
    by_key: dict[str, str] = {}
    order: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        key = _semantic_key(value)
        if key not in by_key:
            by_key[key] = value
            order.append(key)
        elif _specificity(value) > _specificity(by_key[key]):
            by_key[key] = value
    result = [by_key[key] for key in order]
    return result[:limit] if limit else result


def _money(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    formatted = f"{number:,.0f}".replace(",", ".")
    return f"R$ {formatted}"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def _sentence(text: str, fallback: str) -> str:
    content = " ".join(str(text or "").split())
    if not content:
        return fallback
    return content.rstrip(".") + "."


def _category(intelligence: dict[str, Any]) -> str:
    return str(intelligence.get("category") or "")


def _headline(category: str, intelligence: dict[str, Any]) -> str:
    category_key = _normalize(category)
    if category_key in {"power bi", "dashboard"}:
        return "Dashboard Power BI para análise clara dos indicadores"
    if category_key in {"automacao", "python"}:
        return "Automação Python para reduzir tarefas manuais"
    if category_key == "api":
        return "API estruturada para integração entre sistemas"
    if category_key == "full stack":
        return "Aplicação full stack sob medida para operação digital"
    if category_key == "excel":
        return "Planilha Excel organizada para uso claro e confiável"
    if category_key == "web scraping":
        return "Coleta automatizada de dados com tratamento de falhas"
    return f"Solução objetiva para {str(intelligence.get('problem_summary') or 'o projeto')[:70].rstrip('.')}"


def _executive_summary(intelligence: dict[str, Any], strategy: dict[str, Any]) -> str:
    problem = str(intelligence.get("problem_summary") or "O projeto apresenta uma necessidade que precisa ser organizada antes da execução")
    value = str(strategy.get("value_proposition") or "A proposta é entregar uma solução funcional, validada e simples de manter.")
    angle = str(strategy.get("proposal_angle") or "organização e confiabilidade")
    return f"{_sentence(problem, 'O projeto precisa resolver um processo específico.')} {value.rstrip('.')}. A abordagem prioriza {angle}, com validações ao longo do desenvolvimento e entrega orientada ao uso real."


def _understanding(project: Any, intelligence: dict[str, Any], strategy: dict[str, Any]) -> str:
    title = str(_get(project, "title", "projeto") or "projeto")
    category_key = _normalize(_category(intelligence))
    text = _project_text(project)
    if category_key in {"power bi", "dashboard"}:
        return "O objetivo é transformar os dados do projeto em indicadores claros, permitindo acompanhar resultados e tomar decisões com mais confiança. Para isso, a principal dependência é conhecer a fonte dos dados e validar quais métricas devem compor o painel."
    if category_key in {"automacao", "python", "web scraping"}:
        dependency = "validar a API e os arquivos utilizados" if _contains(text, "api") else "receber exemplos reais dos arquivos ou etapas atuais"
        return f"O objetivo é reduzir o trabalho manual e transformar o processo atual em uma rotina mais confiável. O resultado esperado é ganhar tempo, padronizar a execução e facilitar manutenções futuras. A principal dependência é {dependency}."
    if category_key == "full stack":
        return "O objetivo é estruturar uma aplicação web com interface, backend e dados organizados em um fluxo consistente. O impacto esperado é viabilizar uma operação digital mais clara e evolutiva. A principal dependência é confirmar regras, acessos, integrações e prioridades da primeira versão."
    if category_key == "excel":
        return "O objetivo é organizar a planilha para que as informações fiquem mais claras, confiáveis e fáceis de atualizar. A principal dependência é validar as regras, entradas e saídas esperadas antes dos ajustes finais."
    priorities = ", ".join(strategy.get("client_priorities", [])[:3]) or "clareza, confiabilidade e manutenção"
    return f"Entendi que o projeto {title} precisa de uma solução objetiva, com foco em {priorities}. A principal dependência é alinhar o resultado esperado e os materiais de entrada."


def _challenges(project: Any, intelligence: dict[str, Any]) -> list[str]:
    text = _project_text(project)
    challenges: list[str] = []
    if any(_contains(text, term) for term in ("dados", "excel", "csv", "power query", "sql")):
        challenges.append("organizar e validar os dados de entrada")
    if any(_contains(text, term) for term in ("indicador", "dashboard", "power bi", "dax", "kpi")):
        challenges.append("definir indicadores consistentes para análise")
    if any(_contains(text, term) for term in ("processo manual", "automatizar", "rotina", "e mail", "whatsapp")):
        challenges.append("reduzir etapas manuais e repetitivas")
    if any(_contains(text, term) for term in ("api", "integracao", "oauth", "webhook")):
        challenges.append("validar integrações, acessos e dependências externas")
    if any(_contains(text, term) for term in ("react", "frontend", "backend", "fastapi", "saas")):
        challenges.append("organizar frontend, backend e banco em uma solução consistente")
    for risk in intelligence.get("risks", []):
        normalized = _normalize(risk)
        if normalized == "escopo vago":
            challenges.append("confirmar o escopo inicial e os critérios de aceite")
        elif normalized == "dados incompletos":
            challenges.append("trabalhar com dados ainda não totalmente definidos")
        elif normalized == "prazo curto":
            challenges.append("priorizar o essencial para manter prazo realista")
    return _semantic_unique(challenges, 5) or ["validar o escopo e transformar a necessidade em entregáveis objetivos", "testar a solução antes da entrega final"]


def _solution(category: str, intelligence: dict[str, Any], pricing: dict[str, Any]) -> str:
    category_key = _normalize(category)
    if category_key in {"power bi", "dashboard"}:
        return "Primeiro validarei a estrutura dos dados e os indicadores esperados. Em seguida, farei a modelagem, construirei o dashboard e validarei os números principais. Por fim, farei os ajustes finais e entregarei a solução com orientação objetiva de uso."
    if category_key in {"automacao", "python", "web scraping"}:
        return "Começarei mapeando o processo atual, entradas, saídas e exceções. Depois construirei a automação com tratamento de erros, logs e validações intermediárias. Na etapa final, realizarei testes com exemplos reais e entregarei a rotina com instruções de uso."
    if category_key == "full stack":
        return "A execução será organizada por módulos: regras principais, estrutura de dados, backend, frontend e integrações. Cada parte será validada de forma incremental para reduzir retrabalho. A entrega final inclui testes, ajustes e orientação para continuidade."
    return "Primeiro validarei o escopo e os materiais de entrada. Depois construirei a solução em etapas, com validações intermediárias, testes finais e uma entrega organizada para uso e manutenção."


def _deliverables(intelligence: dict[str, Any], pricing: dict[str, Any]) -> list[str]:
    category_key = _normalize(_category(intelligence))
    technologies_text = " ".join(str(item) for item in intelligence.get("relevant_technologies", []))
    all_text = _normalize(" ".join([technologies_text, " ".join(str(item) for item in intelligence.get("risks", [])), " ".join(str(item) for item in intelligence.get("deliverables", []))]))
    if category_key in {"power bi", "dashboard"}:
        items = [
            "Dashboard Power BI funcional",
            "Modelo de dados organizado",
            "Medidas DAX necessárias" if "dax" in _normalize(technologies_text) else "",
            "Indicadores validados",
            "Configuração de atualização" if any(term in all_text for term in ("power query", "dataflow", "atualizacao")) else "",
            "Orientação básica de uso",
            "Uma rodada de ajustes",
        ]
    elif category_key == "excel":
        items = [
            "Planilha funcional",
            "Fórmulas e validações",
            "Automação solicitada" if "automacao" in all_text else "",
            "Área de entrada e saída organizada",
            "Orientação de uso",
            "Uma rodada de ajustes",
        ]
    elif category_key in {"automacao", "python", "web scraping"}:
        items = [
            "Script ou aplicação funcional",
            "Tratamento de erros",
            "Logs básicos",
            "Configuração dos parâmetros",
            "Documentação de execução",
            "Uma rodada de ajustes",
        ]
    elif category_key == "full stack":
        items = [
            "Interface funcional",
            "Backend/API",
            "Banco de dados",
            "Autenticação" if any(term in all_text for term in ("oauth", "login", "autenticacao")) else "",
            "Validação dos fluxos",
            "Instruções de execução ou deploy",
        ]
    else:
        items = [str(item) for item in intelligence.get("deliverables", []) if item]
        items.append("Uma rodada de ajustes")
    return _semantic_unique([item for item in items if item], 7)


def _work_method(category: str) -> list[dict[str, str]]:
    category_key = _normalize(category)
    first = "Validação dos dados, indicadores e resultado esperado." if category_key in {"power bi", "dashboard"} else "Validação do processo, entradas, saídas e critérios de aceite."
    return [
        {"name": "Levantamento", "description": first},
        {"name": "Planejamento", "description": "Definição da estrutura da solução e das entregas prioritárias."},
        {"name": "Desenvolvimento", "description": "Construção da solução com validações intermediárias."},
        {"name": "Validação e entrega", "description": "Testes finais, ajustes combinados e orientação de uso."},
    ]


def _timeline(pricing: dict[str, Any]) -> list[dict[str, str]]:
    hours = int(pricing.get("estimated_hours", 0) or 0)
    if hours <= 8:
        return [{"phase": "Levantamento", "duration": "até 1 dia"}, {"phase": "Desenvolvimento", "duration": "1 a 2 dias"}, {"phase": "Validação e entrega", "duration": "até 1 dia"}]
    if hours <= 36:
        return [{"phase": "Levantamento", "duration": "1 a 2 dias"}, {"phase": "Desenvolvimento", "duration": "3 a 5 dias"}, {"phase": "Validação e entrega", "duration": "1 a 2 dias"}]
    if hours <= 90:
        return [{"phase": "Levantamento", "duration": "2 a 3 dias"}, {"phase": "Desenvolvimento", "duration": "1 a 2 semanas"}, {"phase": "Validação e entrega", "duration": "2 a 4 dias"}]
    return [{"phase": "Levantamento", "duration": "3 a 5 dias"}, {"phase": "Desenvolvimento", "duration": "3 a 6 semanas"}, {"phase": "Validação e entrega", "duration": "1 a 2 semanas"}]


def _technologies(intelligence: dict[str, Any], project: Any) -> list[str]:
    selected = [str(item) for item in intelligence.get("relevant_technologies", []) if item]
    if len(selected) < 2:
        for skill in _get(project, "skills", []) or []:
            if str(skill) not in selected:
                selected.append(str(skill))
    return _semantic_unique(selected, 6)


def _cases(strategy: dict[str, Any]) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for case in strategy.get("relevant_cases", [])[:2]:
        if isinstance(case, dict):
            cases.append({"name": str(case.get("name", "")), "reason": str(case.get("reason", "")), "url": str(case.get("url", ""))})
    return cases


def _proof_points(category: str, strategy: dict[str, Any], cases: list[dict[str, str]]) -> list[str]:
    case_names = {_normalize(case["name"]) for case in cases}
    category_key = _normalize(category)
    raw_points: list[str] = []
    for point in strategy.get("proof_points", []):
        normalized = _normalize(point)
        if not any(name and name in normalized for name in case_names):
            if category_key in {"power bi", "dashboard"} and "77%" in point:
                continue
            raw_points.append(str(point))
    if category_key in {"power bi", "dashboard"}:
        direct = [
            "Experiência com manutenção e evolução de soluções Power BI, Power Query, Dataflows, modelos semânticos e medidas DAX.",
            "Experiência com dashboards corporativos e validação de indicadores para apoio à decisão.",
        ]
        raw_points = direct + raw_points
    return _semantic_unique(raw_points, 3)


def _experience_text(category: str, proof_points: list[str], strategy: dict[str, Any]) -> str:
    category_key = _normalize(category)
    experience = " ".join(str(item) for item in strategy.get("relevant_experience", []))
    if category_key in {"power bi", "dashboard"}:
        return "Tenho experiência com dashboards e processos de dados em ambiente corporativo, incluindo manutenção de soluções Power BI, tratamento de bases, Power Query, Dataflows e medidas DAX."
    if category_key in {"automacao", "python", "web scraping"}:
        metric = next((point for point in proof_points if "75%" in point or "77%" in point), "")
        if metric:
            return "Em projetos internos de automação, já trabalhei com rotinas que reduziram retrabalho e tempo de execução, incluindo consolidação de relatórios, envio de e-mails e processos em Python."
        return "Tenho experiência com automações em Python, tratamento de arquivos, envio automatizado e rotinas com validações para reduzir trabalho manual."
    if category_key == "full stack":
        return "Tenho experiência construindo aplicações com backend, frontend, banco de dados e integrações, mantendo foco em organização técnica e evolução futura."
    if category_key == "excel":
        return "Tenho experiência com planilhas de controle, organização de dados e automações ligadas a processos administrativos e financeiros."
    if experience:
        return f"Tenho experiência relacionada ao projeto, incluindo {experience.split(';')[0].strip()}."
    return "Tenho experiência prática com automação, dados e desenvolvimento de soluções internas voltadas a uso real."


def _investment(pricing: dict[str, Any]) -> str:
    value = _money(pricing.get("suggested_price_brl"))
    hours = int(pricing.get("estimated_hours", 0) or 0)
    project_type = str(pricing.get("project_type") or "")
    scope_by_type = {
        "dashboard_power_bi": "modelagem, desenvolvimento, validação dos indicadores e ajustes finais",
        "automacao_python": "mapeamento do processo, construção da automação, testes e orientação de uso",
        "scraping": "coleta automatizada, tratamento de falhas, testes e orientação de uso",
        "aplicacao_fullstack": "interface, backend, banco de dados, integrações, testes e organização da entrega",
        "ajuste_excel": "ajustes na planilha, validações, testes e uma rodada de ajustes",
        "planilha_automatizada": "organização da planilha, automação solicitada, validações e orientação de uso",
    }
    scope = scope_by_type.get(project_type)
    if scope:
        text = f"O investimento sugerido é de {value}, considerando aproximadamente {hours} horas de trabalho para {scope}."
    else:
        text = f"O investimento sugerido é de {value}, considerando aproximadamente {hours} horas de trabalho, com desenvolvimento, validação e uma rodada de ajustes."
    if pricing.get("requires_scope_validation"):
        text += " O valor é uma estimativa inicial e poderá ser refinado após a validação dos dados e do escopo."
    return text


def _assumptions(pricing: dict[str, Any]) -> list[str]:
    return _semantic_unique([str(item) for item in pricing.get("assumptions", []) if item], 5)


def _questions(intelligence: dict[str, Any], pricing: dict[str, Any]) -> list[str]:
    questions = [str(item) for item in intelligence.get("clarifying_questions", []) if item]
    limit = 3 if float(intelligence.get("scope_confidence", 0.0) or 0.0) >= 0.75 and not pricing.get("requires_scope_validation") else 5
    return _semantic_unique(questions, limit)


def _next_step(strategy: dict[str, Any], category: str, pricing: dict[str, Any]) -> str:
    category_key = _normalize(category)
    if pricing.get("requires_scope_validation") and float(pricing.get("confidence", 0.0) or 0.0) < 0.7:
        return "Como próximo passo, podemos alinhar o resultado esperado e os itens essenciais da primeira entrega."
    if category_key in {"power bi", "dashboard"}:
        return "Como próximo passo, preciso conhecer a fonte dos dados e os principais indicadores que devem compor o painel."
    if category_key in {"automacao", "python", "web scraping"}:
        return "Como próximo passo, preciso entender o processo atual e receber um exemplo dos arquivos utilizados."
    if category_key == "api":
        return "Como próximo passo, preciso validar os sistemas envolvidos e os dados que serão trocados entre eles."
    if category_key == "full stack":
        return "Como próximo passo, preciso alinhar as regras principais, integrações e prioridades da primeira versão."
    if "escopo" in _normalize(" ".join(strategy.get("objections", []))):
        return "Como próximo passo, podemos alinhar o resultado esperado e os itens essenciais da primeira entrega."
    return "Como próximo passo, preciso validar os materiais de entrada e os critérios de aceite."


def _compose_full(
    category: str,
    understanding: str,
    proposed_solution: str,
    deliverables: list[str],
    proof_points: list[str],
    strategy: dict[str, Any],
    investment_summary: str,
    next_step: str,
) -> str:
    deliverable_text = "\n".join(f"- {item[0].lower() + item[1:] if item else item};" for item in deliverables[:6]).rstrip(";") + "."
    proof = _experience_text(category, proof_points, strategy)
    text = (
        "Olá! Analisei o projeto e entendi a necessidade principal.\n\n"
        f"{understanding}\n\n"
        f"{proposed_solution}\n\n"
        f"A entrega pode incluir:\n\n{deliverable_text}\n\n"
        f"{proof}\n\n"
        f"{investment_summary}\n\n"
        f"{next_step}"
    )
    return _fit_words(text, 180, 320, filler="Durante a execução, mantenho comunicação objetiva sobre andamento, decisões técnicas e pontos que precisarem de validação.")


def _timeline_phrase(pricing: dict[str, Any]) -> str:
    hours = int(pricing.get("estimated_hours", 0) or 0)
    if pricing.get("requires_scope_validation"):
        return "prazo a confirmar após validação do escopo"
    if hours <= 8:
        return "aproximadamente 2 a 4 dias úteis"
    if hours <= 36:
        return "aproximadamente 5 a 8 dias úteis"
    if hours <= 90:
        return "entre 2 e 3 semanas"
    return "entre 4 e 8 semanas"


def _compose_short(
    category: str,
    understanding: str,
    deliverables: list[str],
    proof_points: list[str],
    strategy: dict[str, Any],
    pricing: dict[str, Any],
    investment_summary: str,
    next_step: str,
) -> str:
    deliverable_text = "; ".join(deliverables[:4])
    investment_match = re.search(r"(O investimento sugerido é de R\$ [\d\.]+, considerando aproximadamente \d+ horas de trabalho)", investment_summary)
    investment_sentence = (investment_match.group(1) if investment_match else investment_summary.strip()).rstrip(".") + "."
    proof = _experience_text(category, proof_points, strategy).split(".")[0].strip() + "."
    text = (
        f"Olá! {understanding.split('.')[0].strip()}. "
        f"Minha proposta é validar os pontos principais, desenvolver a solução e entregar itens como {deliverable_text}. "
        f"{proof} O prazo estimado é de {_timeline_phrase(pricing)}. "
        f"{investment_sentence} {next_step}"
    )
    return _fit_words(text, 90, 160, filler="Antes de iniciar, valido os pontos críticos para evitar retrabalho e manter o escopo objetivo.")


def _fit_words(text: str, minimum: int, maximum: int, filler: str) -> str:
    cleaned = "\n\n".join(part.strip() for part in text.split("\n\n") if part.strip())
    while _word_count(cleaned) < minimum:
        cleaned += f"\n\n{filler}"
    words = cleaned.split()
    if len(words) <= maximum:
        return cleaned
    truncated = " ".join(words[:maximum]).rstrip(" ,;")
    sentence_end = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
    if sentence_end > len(truncated) * 0.65:
        return truncated[: sentence_end + 1]
    return truncated + "."


def _apply_ai_refinement(proposal: ProposalV2, ai_client: ProposalRefiner | None) -> ProposalV2:
    if ai_client is None:
        return proposal
    refined = ai_client.refine_proposal(
        proposal,
        {
            "immutable_fields": [
                "deliverables",
                "technologies",
                "relevant_cases",
                "proof_points",
                "assumptions",
                "investment_summary",
            ]
        },
    )
    result = dict(proposal)
    for key in ("executive_summary", "understanding", "proposed_solution", "proposal_text", "short_proposal_text"):
        if isinstance(refined.get(key), str) and refined[key].strip():
            result[key] = refined[key].strip()
    return result  # type: ignore[return-value]


def generate_proposal(
    project: Any,
    intelligence: dict[str, Any],
    strategy: dict[str, Any],
    pricing: dict[str, Any],
    knowledge: dict[str, dict[str, Any]],
    ai_client: ProposalRefiner | None = None,
) -> ProposalV2:
    """Gera proposta estruturada determinística, com refinamento opcional."""
    category = _category(intelligence)
    headline = _headline(category, intelligence)
    executive_summary = _executive_summary(intelligence, strategy)
    understanding = _understanding(project, intelligence, strategy)
    challenges = _challenges(project, intelligence)
    solution = _solution(category, intelligence, pricing)
    deliverables = _deliverables(intelligence, pricing)
    work_method = _work_method(category)
    timeline = _timeline(pricing)
    technologies = _technologies(intelligence, project)
    cases = _cases(strategy)
    proof_points = _proof_points(category, strategy, cases)
    investment = _investment(pricing)
    assumptions = _assumptions(pricing)
    questions = _questions(intelligence, pricing)
    next_step = _next_step(strategy, category, pricing)
    proposal_text = _compose_full(category, understanding, solution, deliverables, proof_points, strategy, investment, next_step)
    short_text = _compose_short(category, understanding, deliverables, proof_points, strategy, pricing, investment, next_step)

    proposal: ProposalV2 = {
        "headline": headline,
        "executive_summary": executive_summary,
        "understanding": understanding,
        "identified_challenges": challenges,
        "proposed_solution": solution,
        "deliverables": deliverables,
        "work_method": work_method,
        "timeline": timeline,
        "technologies": technologies,
        "relevant_cases": cases,
        "proof_points": proof_points,
        "investment_summary": investment,
        "assumptions": assumptions,
        "clarifying_questions": questions,
        "next_step": next_step,
        "proposal_text": proposal_text,
        "short_proposal_text": short_text,
    }
    return _apply_ai_refinement(proposal, ai_client)
