from __future__ import annotations

import unittest
import unicodedata

from commercial_strategy import build_commercial_strategy
from knowledge_engine import load_knowledge
from proposal_intelligence import build_proposal_intelligence
from scrapers.base import Project


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


class CommercialStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.knowledge = load_knowledge()

    def _strategy(self, project: Project | dict) -> dict:
        intelligence = build_proposal_intelligence(project)
        return build_commercial_strategy(project, intelligence, self.knowledge)

    def test_power_bi_strategy_focuses_on_dashboard_and_corporate_experience(self) -> None:
        project = Project(
            id="bi",
            platform="workana",
            title="Dashboard Power BI para indicadores comerciais",
            url="https://example.com/bi",
            description=(
                "Preciso criar um dashboard Power BI com Power Query, Dataflows, "
                "medidas DAX e indicadores confiaveis para acompanhamento comercial."
            ),
            skills=["Power BI", "DAX", "Power Query"],
        )

        strategy = self._strategy(project)
        joined_experience = " ".join(strategy["relevant_experience"]).lower()
        all_text = " ".join(str(value) for value in strategy.values()).lower()

        self.assertIn("dados", strategy["positioning"])
        self.assertIn("dashboard", strategy["positioning"])
        self.assertIn(strategy["proposal_angle"], {"clareza para decisao", "organizacao e confiabilidade"})
        self.assertTrue("power bi" in joined_experience or "dax" in joined_experience or "dataflows" in joined_experience)
        self.assertNotIn("react", all_text)

    def test_python_automation_strategy_reduces_rework(self) -> None:
        project = Project(
            id="auto",
            platform="99freelas",
            title="Automacao Python para relatorios e e-mails",
            url="https://example.com/auto",
            description=(
                "Tenho um processo manual de consolidar arquivos Excel e enviar "
                "e-mails. Quero automatizar a rotina com Python e logs."
            ),
            skills=["Python", "Excel"],
        )

        strategy = self._strategy(project)
        proof_text = _plain(" ".join(strategy["proof_points"]))

        self.assertEqual(strategy["proposal_angle"], "reducao de retrabalho")
        self.assertTrue("automacao" in proof_text or "reducao" in proof_text or "relatorios" in proof_text)
        self.assertTrue("processo" in strategy["cta"] or "arquivos" in strategy["cta"])

    def test_full_stack_strategy_uses_coherent_cases_and_objections(self) -> None:
        project = {
            "id": "fs",
            "platform": "freelancer",
            "title": "SaaS full stack com dashboard e integracao OAuth",
            "url": "https://example.com/fs",
            "description": (
                "Preciso de um sistema web SaaS com frontend React, backend FastAPI, "
                "PostgreSQL, autenticacao, dashboard, integracao OAuth, API externa "
                "e deploy com Docker."
            ),
            "skills": ["React", "FastAPI", "PostgreSQL", "Docker"],
        }

        strategy = self._strategy(project)
        objection_text = " ".join(strategy["objections"])

        self.assertIn("full stack", strategy["positioning"])
        self.assertTrue(strategy["relevant_cases"])
        self.assertTrue(any(case["reason"] for case in strategy["relevant_cases"]))
        self.assertTrue(any(term in objection_text for term in ("integracao", "prazo", "escopo")))

    def test_limits_are_enforced(self) -> None:
        project = Project(
            id="limits",
            platform="workana",
            title="SaaS dashboard com automacao, API, ETL e Power BI",
            url="https://example.com/limits",
            description=(
                "Sistema SaaS com React, FastAPI, PostgreSQL, Docker, dashboard, "
                "ETL, API externa, automacao em Python, Power BI, prazo curto e dados incompletos."
            ),
            skills=["React", "FastAPI", "Python", "Power BI", "PostgreSQL"],
        )

        strategy = self._strategy(project)

        self.assertLessEqual(len(strategy["proof_points"]), 3)
        self.assertLessEqual(len(strategy["relevant_cases"]), 2)
        self.assertLessEqual(len(strategy["objections"]), 3)

    def test_vague_project_asks_for_validation_without_definitive_timeline_claim(self) -> None:
        project = Project(
            id="vague",
            platform="workana",
            title="Ajustar planilha urgente",
            url="https://example.com/vague",
            description="Preciso ajustar uma planilha simples urgente.",
            skills=["Excel"],
        )

        intelligence = build_proposal_intelligence(project)
        strategy = build_commercial_strategy(project, intelligence, self.knowledge)
        avoid_text = " ".join(strategy["claims_to_avoid"]).lower()

        self.assertIn("escopo vago", intelligence["risks"])
        self.assertIn("validar", strategy["cta"])
        self.assertIn("prazo definitivo sem escopo validado", avoid_text)


if __name__ == "__main__":
    unittest.main()
