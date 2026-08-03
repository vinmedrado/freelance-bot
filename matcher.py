"""Matcher determinístico baseado na base de conhecimento em ``knowledge/``."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from knowledge_engine import build_legacy_profile, load_knowledge, select_relevant_context


def load_profile() -> dict[str, Any]:
    """Compatibilidade com dashboard/PDF e chamadas existentes."""
    return build_legacy_profile()


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _contains(haystack: str, needle: str) -> bool:
    needle = _normalize(needle)
    if not needle:
        return False
    if " " in needle:
        return needle in haystack
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


def score_project(project: Any, profile: dict | None = None) -> float:
    """Calcula score de 0 a 100 usando skills, serviços, cases e bloqueios."""
    kb = load_knowledge()
    matching = kb["project_matching"]
    points = matching.get("pontuacao", {})
    text = _normalize(
        f"{getattr(project, 'title', '')} {getattr(project, 'description', '')} "
        f"{' '.join(getattr(project, 'skills', []) or [])}"
    )

    for blocked in matching.get("skills_bloqueio", []):
        if _contains(text, blocked):
            return 0.0

    context = select_relevant_context(project)
    score = 0.0

    exact_weight = float(points.get("skill_exata", 15))
    category_weight = float(points.get("categoria_relacionada", 10))
    case_weight = float(points.get("case_semelhante", 12))
    secondary_weight = float(points.get("tecnologia_secundaria", 4))

    specialty_hits = sum(item.get("score", 0) for item in context["specialties"])
    service_hits = len(context["services"])
    case_hits = len(context["cases"])

    score += min(specialty_hits, 3) * exact_weight
    score += min(service_hits, 2) * category_weight
    score += min(case_hits, 2) * case_weight

    # Pequeno reforço por tecnologia conhecida, sem dominar o score.
    all_technologies = [
        tech
        for group in kb["technologies"].get("tecnologias", {}).values()
        if isinstance(group, list)
        for tech in group
    ]
    tech_hits = sum(1 for tech in all_technologies if _contains(text, tech))
    score += min(tech_hits, 3) * secondary_weight

    # Anúncios quase sem contexto exigem revisão manual e recebem penalidade.
    if len(text.split()) < 12:
        score += float(points.get("escopo_vago", -10))

    return round(max(0.0, min(score, 100.0)), 1)


def filter_relevant(
    projects: list,
    profile: dict | None = None,
    min_score: float = 25.0,
    only_free_to_bid: bool = True,
) -> list:
    results = []
    for project in projects:
        if only_free_to_bid and not project.is_free_to_bid:
            continue
        score = score_project(project, profile)
        if score >= min_score:
            results.append((score, project))
    results.sort(key=lambda item: item[0], reverse=True)
    return results
