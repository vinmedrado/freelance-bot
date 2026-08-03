from __future__ import annotations

import unittest

from commercial_strategy import build_commercial_strategy
from knowledge_engine import load_knowledge
from pricing_engine import calculate_pricing
from proposal_intelligence import build_proposal_intelligence
from scrapers.base import Project


def _combined_multiplier(result: dict) -> float:
    multiplier = 1.0
    for adjustment in result["adjustments"]:
        multiplier *= float(adjustment["multiplier"])
    return round(multiplier, 4)


class PricingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.knowledge = load_knowledge()

    def _price(self, project: Project | dict) -> dict:
        intelligence = build_proposal_intelligence(project)
        strategy = build_commercial_strategy(project, intelligence, self.knowledge)
        return calculate_pricing(project, intelligence, strategy, self.knowledge)

    def test_simple_excel_adjustment_respects_range_and_minimum(self) -> None:
        project = Project(
            id="excel",
            platform="workana",
            title="Ajuste em planilha Excel",
            url="https://example.com/excel",
            description="Preciso ajustar formulas e organizar uma planilha Excel existente com regras claras.",
            skills=["Excel"],
        )

        result = self._price(project)

        self.assertEqual(result["project_type"], "ajuste_excel")
        self.assertGreaterEqual(result["estimated_hours"], 3)
        self.assertLessEqual(result["estimated_hours"], 8)
        self.assertLessEqual(result["suggested_price_brl"], 700)
        self.assertGreaterEqual(result["suggested_price_brl"], result["minimum_price_brl"])
        self.assertGreaterEqual(result["suggested_price_brl"], 250)
        self.assertGreaterEqual(result["confidence"], 0.80)
        self.assertFalse(result["requires_scope_validation"])

    def test_medium_power_bi_dashboard_has_coherent_reason(self) -> None:
        project = Project(
            id="bi",
            platform="workana",
            title="Dashboard Power BI para vendas",
            url="https://example.com/bi",
            description=(
                "Criar dashboard Power BI com modelagem dos dados, Power Query, "
                "medidas DAX, indicadores comerciais e validacao dos numeros."
            ),
            skills=["Power BI", "DAX", "Power Query"],
        )

        result = self._price(project)
        reason = result["pricing_reason"].lower()

        self.assertEqual(result["project_type"], "dashboard_power_bi")
        self.assertGreaterEqual(result["estimated_hours"], 20)
        self.assertLessEqual(result["estimated_hours"], 36)
        self.assertGreaterEqual(result["hourly_rate_brl"], 75)
        self.assertLessEqual(result["hourly_rate_brl"], 95)
        self.assertGreaterEqual(result["suggested_price_brl"], 1800)
        self.assertLessEqual(result["suggested_price_brl"], 3400)
        self.assertLess(result["suggested_price_brl"], 4000)
        self.assertLess(result["minimum_price_brl"], result["suggested_price_brl"])
        self.assertLess(result["suggested_price_brl"], result["maximum_price_brl"])
        self.assertIn("modelagem", reason)
        self.assertIn("dashboard", reason)
        self.assertIn("validacao", reason)
        self.assertGreaterEqual(result["confidence"], 0.70)
        self.assertFalse(result["requires_scope_validation"])

    def test_python_automation_with_integration_is_priced_above_simple_excel(self) -> None:
        simple = self._price(Project(
            id="simple",
            platform="workana",
            title="Ajuste em Excel",
            url="https://example.com/simple",
            description="Ajustar formulas de uma planilha Excel.",
            skills=["Excel"],
        ))
        project = Project(
            id="auto",
            platform="99freelas",
            title="Automacao Python com API",
            url="https://example.com/auto",
            description=(
                "Automatizar processo manual com Python, consumir API externa, "
                "documentada, processar arquivos Excel, gerar logs e enviar e-mails."
            ),
            skills=["Python", "API", "Excel"],
        )

        result = self._price(project)
        factors = {adjustment["factor"] for adjustment in result["adjustments"]}
        assumptions = " ".join(result["assumptions"]).lower()

        self.assertIn("integration", factors)
        self.assertNotIn("risk", factors)
        self.assertGreaterEqual(result["estimated_hours"], 20)
        self.assertLessEqual(result["estimated_hours"], 42)
        self.assertGreaterEqual(result["hourly_rate_brl"], 80)
        self.assertLessEqual(result["hourly_rate_brl"], 105)
        self.assertGreaterEqual(result["suggested_price_brl"], 2000)
        self.assertLessEqual(result["suggested_price_brl"], 4500)
        self.assertGreater(result["suggested_price_brl"], simple["suggested_price_brl"])
        self.assertIn("integracoes externas", assumptions)
        self.assertFalse(result["requires_scope_validation"])

    def test_complex_full_stack_requires_validation(self) -> None:
        project = {
            "id": "full",
            "platform": "freelancer",
            "title": "SaaS full stack com dashboard e OAuth",
            "url": "https://example.com/full",
            "description": (
                "Sistema web SaaS com frontend React, backend FastAPI, PostgreSQL, "
                "autenticacao OAuth, API externa, dashboard, deploy com Docker e prazo a definir."
            ),
            "skills": ["React", "FastAPI", "PostgreSQL", "Docker"],
        }

        result = self._price(project)

        self.assertEqual(result["project_type"], "aplicacao_fullstack")
        self.assertEqual(result["complexity"], "high")
        self.assertGreaterEqual(result["estimated_hours"], 150)
        self.assertLessEqual(result["estimated_hours"], 280)
        self.assertGreaterEqual(result["hourly_rate_brl"], 95)
        self.assertLessEqual(result["hourly_rate_brl"], 125)
        self.assertTrue(result["requires_scope_validation"])
        self.assertLess(result["minimum_price_brl"], result["suggested_price_brl"])
        self.assertLess(result["suggested_price_brl"], result["maximum_price_brl"])
        self.assertLessEqual(result["suggested_price_brl"], result["maximum_price_brl"])
        self.assertLessEqual(_combined_multiplier(result), 1.60)

    def test_vague_project_reduces_confidence_and_requires_validation(self) -> None:
        project = Project(
            id="vague",
            platform="workana",
            title="Automacao urgente",
            url="https://example.com/vague",
            description="Preciso automatizar uma coisa simples urgente.",
            skills=["Python"],
        )

        result = self._price(project)
        assumptions = " ".join(result["assumptions"]).lower()

        self.assertLess(result["confidence"], 0.65)
        self.assertTrue(result["requires_scope_validation"])
        self.assertIn("escopo", assumptions)

    def test_low_budget_does_not_force_price_below_minimum(self) -> None:
        project = Project(
            id="budget",
            platform="workana",
            title="Dashboard Power BI",
            url="https://example.com/budget",
            description="Criar dashboard Power BI com indicadores, DAX e validacao.",
            skills=["Power BI", "DAX"],
            budget_text="R$ 200",
        )

        result = self._price(project)
        combined = " ".join(result["assumptions"] + [result["pricing_reason"]]).lower()

        self.assertGreaterEqual(result["suggested_price_brl"], 900)
        self.assertIn("orcamento", combined)
        self.assertTrue(result["requires_scope_validation"])

    def test_determinism(self) -> None:
        project = Project(
            id="det",
            platform="99freelas",
            title="Scraping com Playwright",
            url="https://example.com/det",
            description="Coletar dados com Playwright, tratar falhas e exportar CSV.",
            skills=["Python", "Playwright"],
        )

        self.assertEqual(self._price(project), self._price(project))

    def test_limits(self) -> None:
        project = Project(
            id="limits",
            platform="workana",
            title="API backend",
            url="https://example.com/limits",
            description="Criar API REST com FastAPI, banco PostgreSQL, autenticacao e documentacao.",
            skills=["FastAPI", "PostgreSQL"],
        )

        result = self._price(project)
        value_hour = self.knowledge["pricing"]["valor_hora"]

        self.assertGreaterEqual(result["suggested_price_brl"], result["minimum_price_brl"])
        self.assertLessEqual(result["suggested_price_brl"], result["maximum_price_brl"])
        self.assertGreaterEqual(result["hourly_rate_brl"], value_hour["minimo"])
        self.assertLessEqual(result["hourly_rate_brl"], value_hour["maximo"])
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_medium_power_bi_does_not_use_ceiling_automatically(self) -> None:
        result = self._price(Project(
            id="bi-ceiling",
            platform="workana",
            title="Dashboard Power BI financeiro",
            url="https://example.com/bi-ceiling",
            description=(
                "Criar dashboard Power BI com modelagem, Power Query, DAX, "
                "validacao de indicadores financeiros e uma fonte de dados estruturada."
            ),
            skills=["Power BI", "DAX", "Power Query"],
        ))

        self.assertNotEqual(result["suggested_price_brl"], result["maximum_price_brl"])
        self.assertLess(result["suggested_price_brl"], 4000)
        self.assertFalse(result["requires_scope_validation"])


if __name__ == "__main__":
    unittest.main()
