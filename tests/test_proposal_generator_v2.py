from __future__ import annotations

import unittest

from commercial_strategy import build_commercial_strategy
from knowledge_engine import load_knowledge
from pricing_engine import calculate_pricing
from proposal_generator_v2 import generate_proposal
from proposal_intelligence import build_proposal_intelligence
from scrapers.base import Project


def _words(text: str) -> int:
    return len(text.split())


class ProposalGeneratorV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.knowledge = load_knowledge()

    def _proposal(self, project: Project | dict) -> dict:
        intelligence = build_proposal_intelligence(project)
        strategy = build_commercial_strategy(project, intelligence, self.knowledge)
        pricing = calculate_pricing(project, intelligence, strategy, self.knowledge)
        return generate_proposal(project, intelligence, strategy, pricing, self.knowledge)

    def test_power_bi_proposal_is_specific(self) -> None:
        project = Project(
            id="bi",
            platform="workana",
            title="Dashboard Power BI para vendas",
            url="https://example.com/bi",
            description="Criar dashboard Power BI com modelagem dos dados, Power Query, medidas DAX, indicadores comerciais e validacao dos numeros.",
            skills=["Power BI", "DAX", "Power Query"],
        )

        proposal = self._proposal(project)
        challenges = " ".join(proposal["identified_challenges"]).lower()
        deliverables = " ".join(proposal["deliverables"]).lower()
        technologies = set(proposal["technologies"])

        self.assertIn("Dashboard Power BI", proposal["headline"])
        self.assertTrue("dados" in challenges or "indicadores" in challenges)
        self.assertIn("dashboard", deliverables)
        self.assertTrue({"Power BI", "DAX", "Power Query"} & technologies)
        self.assertIn("R$ 2.400", proposal["investment_summary"])

    def test_python_automation_mentions_manual_work_and_integration(self) -> None:
        project = Project(
            id="auto",
            platform="99freelas",
            title="Automacao Python com API",
            url="https://example.com/auto",
            description="Automatizar processo manual com Python, consumir API externa documentada, processar arquivos Excel, gerar logs e enviar e-mails.",
            skills=["Python", "API", "Excel"],
        )

        proposal = self._proposal(project)
        solution = proposal["proposed_solution"].lower()
        text = proposal["proposal_text"].lower()

        self.assertIn("tarefas manuais", proposal["headline"].lower())
        self.assertGreaterEqual(len(proposal["work_method"]), 3)
        self.assertTrue("api" in text or "integra" in text)
        self.assertIn("processo atual", proposal["next_step"])
        self.assertIn("processo", solution)

    def test_full_stack_contains_core_parts_and_scope_notes(self) -> None:
        project = {
            "id": "full",
            "platform": "freelancer",
            "title": "SaaS full stack com dashboard e OAuth",
            "url": "https://example.com/full",
            "description": "Sistema web SaaS com frontend React, backend FastAPI, PostgreSQL, autenticacao OAuth, API externa, dashboard, deploy com Docker e prazo a definir.",
            "skills": ["React", "FastAPI", "PostgreSQL", "Docker"],
        }

        proposal = self._proposal(project)
        solution = proposal["proposed_solution"].lower()
        timeline = " ".join(item["duration"] for item in proposal["timeline"])
        assumptions = " ".join(proposal["assumptions"]).lower()

        self.assertIn("frontend", solution)
        self.assertIn("backend", solution)
        self.assertIn("dados", solution)
        self.assertTrue("3 a 6 semanas" in timeline or "1 a 2 semanas" in timeline)
        self.assertTrue("escopo" in assumptions or "integra" in assumptions)
        self.assertLessEqual(len(proposal["relevant_cases"]), 2)

    def test_vague_project_uses_questions_and_initial_estimate(self) -> None:
        project = Project(
            id="vague",
            platform="workana",
            title="Automacao urgente",
            url="https://example.com/vague",
            description="Preciso automatizar uma coisa simples urgente.",
            skills=["Python"],
        )

        proposal = self._proposal(project)

        self.assertTrue(proposal["clarifying_questions"])
        self.assertIn("estimativa inicial", proposal["investment_summary"])
        self.assertIn("alinhar", proposal["next_step"])

    def test_limits_and_lengths(self) -> None:
        project = Project(
            id="limits",
            platform="workana",
            title="Dashboard Power BI com API",
            url="https://example.com/limits",
            description="Criar dashboard Power BI com API externa, modelagem, Power Query, DAX, validacao e documentacao.",
            skills=["Power BI", "DAX", "Power Query", "Python", "React", "Docker", "PostgreSQL"],
        )

        proposal = self._proposal(project)

        self.assertLessEqual(len(proposal["relevant_cases"]), 2)
        self.assertLessEqual(len(proposal["proof_points"]), 3)
        self.assertLessEqual(len(proposal["technologies"]), 6)
        self.assertGreaterEqual(_words(proposal["proposal_text"]), 180)
        self.assertLessEqual(_words(proposal["proposal_text"]), 320)
        self.assertGreaterEqual(_words(proposal["short_proposal_text"]), 90)
        self.assertLessEqual(_words(proposal["short_proposal_text"]), 160)

    def test_determinism_without_ai(self) -> None:
        project = Project(
            id="det",
            platform="99freelas",
            title="Ajuste em Excel",
            url="https://example.com/det",
            description="Ajustar formulas de uma planilha Excel com regras claras.",
            skills=["Excel"],
        )

        self.assertEqual(self._proposal(project), self._proposal(project))

    def test_truth_does_not_invent_cases_metrics_or_technologies(self) -> None:
        project = Project(
            id="truth",
            platform="workana",
            title="Script Python simples",
            url="https://example.com/truth",
            description="Preciso de um script Python para renomear arquivos em uma pasta.",
            skills=["Python"],
        )

        proposal = self._proposal(project)
        allowed_techs = {"Python"}

        self.assertEqual(proposal["relevant_cases"], [])
        self.assertTrue(set(proposal["technologies"]).issubset(allowed_techs))
        self.assertNotIn("77%", proposal["proposal_text"])

    def test_text_preserves_known_accents(self) -> None:
        proposal = self._proposal(Project(
            id="accent",
            platform="workana",
            title="Automação Python",
            url="https://example.com/accent",
            description="Automatizar processo manual com integração e validação.",
            skills=["Python"],
        ))
        text = " ".join(str(value) for value in proposal.values())

        for word in ("validação", "solução", "automação", "integração"):
            self.assertIn(word, text.lower())

    def test_semantic_duplicate_deliverables_are_removed(self) -> None:
        proposal = self._proposal(Project(
            id="dupes",
            platform="workana",
            title="Dashboard Power BI",
            url="https://example.com/dupes",
            description="Criar dashboard Power BI com indicadores, DAX, Power Query e validação.",
            skills=["Power BI", "DAX", "Power Query"],
        ))
        normalized = [item.lower() for item in proposal["deliverables"]]

        self.assertIn("dashboard power bi funcional", normalized)
        self.assertNotIn("dashboard", normalized)
        self.assertIn("indicadores validados", normalized)
        self.assertNotIn("indicadores", normalized)

    def test_power_bi_prioritizes_direct_experience_and_not_77_metric(self) -> None:
        proposal = self._proposal(Project(
            id="bi-proof",
            platform="workana",
            title="Dashboard Power BI comercial",
            url="https://example.com/bi-proof",
            description="Criar dashboard Power BI com indicadores comerciais, Power Query, DAX e validação dos dados.",
            skills=["Power BI", "DAX", "Power Query"],
        ))
        proof_text = " ".join(proposal["proof_points"]).lower()

        self.assertTrue(any(term in proof_text for term in ("power bi", "dax", "power query", "dashboard")))
        self.assertNotIn("77%", proof_text)
        self.assertNotIn("77%", proposal["proposal_text"])

    def test_cta_does_not_repeat_scope(self) -> None:
        proposal = self._proposal(Project(
            id="cta",
            platform="workana",
            title="Dashboard Power BI",
            url="https://example.com/cta",
            description="Criar dashboard Power BI com indicadores e validação.",
            skills=["Power BI"],
        ))

        self.assertLessEqual(proposal["next_step"].lower().count("escopo"), 1)

    def test_short_proposal_uses_natural_timeline(self) -> None:
        proposal = self._proposal(Project(
            id="short",
            platform="workana",
            title="Dashboard Power BI",
            url="https://example.com/short",
            description="Criar dashboard Power BI com indicadores, DAX e validação.",
            skills=["Power BI", "DAX"],
        ))

        self.assertNotIn("Levantamento:", proposal["short_proposal_text"])
        self.assertNotIn("Desenvolvimento:", proposal["short_proposal_text"])


if __name__ == "__main__":
    unittest.main()
