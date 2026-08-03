"""Validação local rápida, sem scraping e sem consumo da API Groq."""
from knowledge_engine import build_legacy_profile, load_knowledge, select_relevant_context
from matcher import score_project
from scrapers.base import Project


def main() -> None:
    knowledge = load_knowledge()
    profile = build_legacy_profile(knowledge)
    sample = Project(
        id="validation",
        platform="local",
        title="Dashboard Power BI com tratamento de dados",
        url="http://localhost",
        description="Criar indicadores, Power Query e medidas DAX.",
        skills=["Power BI", "DAX", "Power Query"],
    )
    context = select_relevant_context(sample)
    assert len(knowledge) == 11
    assert profile["nome"]
    assert score_project(sample) > 0
    assert context["specialties"]
    print("OK - base de conhecimento carregada")
    print(f"Perfil: {profile['nome']} | {profile['titulo']}")
    print(f"Score do teste: {score_project(sample)}")
    print("Especialidades:", ", ".join(item["id"] for item in context["specialties"]))


if __name__ == "__main__":
    main()
