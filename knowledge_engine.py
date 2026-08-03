"""Carregamento e seleção contextual da base profissional em ``knowledge/``.

A camada mantém compatibilidade com o restante do sistema ao expor um perfil
resumido para o dashboard/PDF e um contexto seletivo para matcher e Groq.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
REQUIRED_FILES = (
    "identity.yaml",
    "experience.yaml",
    "services.yaml",
    "specialties.yaml",
    "technologies.yaml",
    "portfolio.yaml",
    "writing_style.yaml",
    "proposals.yaml",
    "negotiation.yaml",
    "pricing.yaml",
    "project_matching.yaml",
)


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo obrigatório não encontrado: {path}")
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"O arquivo {path.name} precisa conter um objeto YAML.")
    return data


@lru_cache(maxsize=1)
def load_knowledge() -> dict[str, dict[str, Any]]:
    """Carrega e valida todos os YAMLs uma única vez por processo."""
    return {
        Path(filename).stem: _load_yaml(KNOWLEDGE_DIR / filename)
        for filename in REQUIRED_FILES
    }


def clear_knowledge_cache() -> None:
    """Útil para testes ou edição dos YAMLs sem reiniciar o interpretador."""
    load_knowledge.cache_clear()


def build_legacy_profile(knowledge: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Cria o formato esperado pelo dashboard, PDF e código legado."""
    kb = knowledge or load_knowledge()
    identity = kb["identity"]
    experience = kb["experience"]
    technologies = kb["technologies"].get("tecnologias", {})
    pricing = kb["pricing"]
    matching = kb["project_matching"]

    all_skills: list[str] = []
    for group in technologies.values():
        if isinstance(group, list):
            all_skills.extend(str(item).lower() for item in group)

    # Remove duplicados preservando ordem.
    unique_skills = list(dict.fromkeys(all_skills))

    return {
        "nome": identity.get("nome_profissional") or identity.get("nome", "Vinicius Medrado"),
        "titulo": identity.get("titulo_principal", "Analista de Dados e Automação"),
        "resumo": experience.get("resumo_profissional") or identity.get("posicionamento", ""),
        "nivel": "pleno",
        "skills_principais": unique_skills,
        "skills_secundarias": [],
        "skills_bloqueio": matching.get("skills_bloqueio", []),
        "faixa_valor_hora_brl": {
            "min": pricing.get("valor_hora", {}).get("minimo", 50),
            "max": pricing.get("valor_hora", {}).get("maximo", 150),
        },
        "links": identity.get("links", {}),
    }


def _project_text(project: Any) -> str:
    skills = getattr(project, "skills", []) or []
    return _normalize(
        " ".join(
            [
                getattr(project, "title", "") or "",
                getattr(project, "description", "") or "",
                " ".join(map(str, skills)),
            ]
        )
    )


def _phrase_present(phrase: str, haystack: str) -> bool:
    normalized = _normalize(phrase)
    if not normalized:
        return False
    # Termos simples usam limite de palavra para reduzir falsos positivos.
    if " " not in normalized:
        return re.search(rf"\b{re.escape(normalized)}\b", haystack) is not None
    return normalized in haystack


def select_relevant_context(project: Any, max_cases: int = 2) -> dict[str, Any]:
    """Seleciona somente conhecimento aderente ao anúncio atual."""
    kb = load_knowledge()
    haystack = _project_text(project)

    matched_specialties: list[dict[str, Any]] = []
    for name, spec in kb["specialties"].get("especialidades", {}).items():
        keywords = spec.get("palavras_chave", [])
        hits = [kw for kw in keywords if _phrase_present(kw, haystack)]
        if hits:
            matched_specialties.append(
                {
                    "id": name,
                    "score": len(hits),
                    "palavras_encontradas": hits,
                    "experiencias_relevantes": spec.get("experiencias_relevantes", []),
                }
            )
    matched_specialties.sort(key=lambda item: item["score"], reverse=True)

    matched_services: list[dict[str, Any]] = []
    for service in kb["services"].get("servicos", []):
        searchable = " ".join(
            [service.get("id", ""), service.get("nome", ""), *service.get("entregas", [])]
        )
        terms = [token for token in _normalize(searchable).split() if len(token) >= 4]
        score = sum(1 for token in set(terms) if re.search(rf"\b{re.escape(token)}\b", haystack))
        if score:
            matched_services.append({**service, "score": score})
    matched_services.sort(key=lambda item: item["score"], reverse=True)

    matched_cases: list[dict[str, Any]] = []
    for case in kb["portfolio"].get("projetos", []):
        triggers = case.get("usar_quando", [])
        trigger_hits = [trigger for trigger in triggers if _phrase_present(trigger, haystack)]
        tech_hits = [tech for tech in case.get("tecnologias", []) if _phrase_present(tech, haystack)]
        score = len(trigger_hits) * 3 + len(tech_hits)
        if score:
            matched_cases.append(
                {
                    **case,
                    "score": score,
                    "aderencia": list(dict.fromkeys(trigger_hits + tech_hits)),
                }
            )
    matched_cases.sort(key=lambda item: item["score"], reverse=True)

    return {
        "identity": kb["identity"],
        "experience_summary": kb["experience"].get("resumo_profissional", ""),
        "verified_results": kb["experience"].get("resultados_comprovados", []),
        "specialties": matched_specialties[:3],
        "services": matched_services[:3],
        "cases": matched_cases[:max_cases],
        "writing_style": kb["writing_style"],
        "proposal_rules": kb["proposals"],
        "pricing": kb["pricing"],
        "negotiation": kb["negotiation"],
        "matching": kb["project_matching"],
    }


def context_as_json(project: Any) -> str:
    return json.dumps(select_relevant_context(project), ensure_ascii=False, indent=2)
