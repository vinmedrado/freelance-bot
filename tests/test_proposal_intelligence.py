from __future__ import annotations

import unittest

from scrapers.base import Project
from proposal_intelligence import build_proposal_intelligence


class ProposalIntelligenceTests(unittest.TestCase):
    def test_power_bi_dashboard_selects_related_context_only(self) -> None:
        project = Project(
            id="p1",
            platform="workana",
            title="Dashboard Power BI para indicadores comerciais",
            url="https://example.com/p1",
            description=(
                "Preciso criar um dashboard Power BI com Power Query, medidas DAX "
                "e indicadores de vendas a partir de planilhas Excel."
            ),
            skills=["Power BI", "DAX", "Excel"],
            budget_text="R$ 1.500",
        )

        result = build_proposal_intelligence(project)

        self.assertIn(result["category"], {"Power BI", "Dashboard"})
        self.assertEqual(result["complexity"], "medium")
        self.assertIn("Power BI", result["relevant_technologies"])
        self.assertIn("DAX", result["relevant_technologies"])
        self.assertNotIn("React", result["relevant_technologies"])
        self.assertTrue(any(service["id"] == "power_bi" for service in result["relevant_services"]))
        self.assertLessEqual(len(result["relevant_cases"]), 2)
        self.assertIn("Dashboard", result["deliverables"])

    def test_python_alone_does_not_select_case_without_problem_similarity(self) -> None:
        project = Project(
            id="p2",
            platform="99freelas",
            title="Script Python simples",
            url="https://example.com/p2",
            description="Preciso de um script Python para renomear arquivos em uma pasta.",
            skills=["Python"],
        )

        result = build_proposal_intelligence(project)

        self.assertEqual(result["category"], "Python")
        self.assertEqual(result["relevant_technologies"], ["Python"])
        self.assertEqual(result["relevant_cases"], [])

    def test_full_stack_integration_is_high_complexity_with_risks(self) -> None:
        project = {
            "id": "p3",
            "platform": "freelancer",
            "title": "SaaS full stack com integração OAuth",
            "url": "https://example.com/p3",
            "description": (
                "Quero um sistema web SaaS com frontend React, backend FastAPI, "
                "PostgreSQL, autenticação, integração OAuth, API externa, deploy "
                "com Docker e área de dashboard em tempo real."
            ),
            "skills": ["React", "FastAPI", "PostgreSQL", "Docker"],
            "budget_text": "A combinar",
        }

        result = build_proposal_intelligence(project)

        self.assertEqual(result["category"], "Full Stack")
        self.assertEqual(result["complexity"], "high")
        self.assertIn("integrações externas", result["risks"])
        self.assertIn("React", result["relevant_technologies"])
        self.assertIn("FastAPI", result["relevant_technologies"])
        self.assertTrue(result["pricing_context"]["risk_count"] >= 1)


if __name__ == "__main__":
    unittest.main()
