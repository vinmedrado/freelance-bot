"""Análise comercial contextual com Groq."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from groq import Groq

from commercial_strategy import build_commercial_strategy
from knowledge_engine import load_knowledge, select_relevant_context
from pricing_engine import calculate_pricing
from project_validation import validate_project_output
from proposal_generator_v2 import generate_proposal
from proposal_intelligence import build_proposal_intelligence

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você atua como consultor comercial técnico de Vinicius Medrado.
Sua tarefa é avaliar projetos freelance, estimar esforço/preço e redigir uma proposta verdadeira,
personalizada, natural e pronta para revisão humana.

REGRAS INEGOCIÁVEIS:
- Use somente fatos presentes no CONTEXTO PROFISSIONAL SELECIONADO.
- Nunca invente experiência, case, resultado, certificação ou tecnologia.
- Demonstre entendimento do problema sem copiar o anúncio.
- Cite no máximo 1 case, apenas quando houver aderência real.
- Não mencione IA, prompt, matcher, score interno ou base de conhecimento.
- Não informe preço ou horas dentro de proposta_texto.
- Use a precificacao recebida como fonte principal para estimativa_horas e valor_sugerido_brl.
- Não altere livremente o preço calculado pelo motor determinístico.
- Não use “Prezado”, “Caro cliente”, “sou apaixonado”, “tenho certeza” ou elogios vazios.
- Evite linguagem genérica e frases que serviriam para qualquer projeto.
- Proposta entre 130 e 240 palavras, em primeira pessoa, com tom consultivo e direto.
- Caso o escopo seja insuficiente, ainda gere uma proposta prudente e indique as perguntas críticas em perguntas_escopo.
- Se o projeto estiver fora do escopo ou exigir skill bloqueada, vale_a_pena=false.

PREÇO:
- Respeite os mínimos, máximos e multiplicadores informados no contexto.
- Considere desenvolvimento, testes, comunicação e correções.
- Não force o orçamento do cliente quando ele for incompatível com o escopo.

Retorne SOMENTE JSON válido no formato:
{
  "vale_a_pena": true,
  "motivo_curto": "frase objetiva",
  "categoria": "categoria principal",
  "complexidade": "baixa|media|alta",
  "estimativa_horas": 20,
  "valor_hora_brl": 85,
  "valor_sugerido_brl": 1700,
  "prazo_estimado_dias_uteis": 7,
  "case_utilizado": "nome ou vazio",
  "perguntas_escopo": ["pergunta 1"],
  "proposta_texto": "texto pronto"
}
"""


def _client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Defina GROQ_API_KEY no arquivo .env")
    return Groq(api_key=api_key)


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _validate_result(result: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "vale_a_pena": False,
        "motivo_curto": "Resposta incompleta da IA",
        "categoria": "não classificado",
        "complexidade": "media",
        "estimativa_horas": 0,
        "valor_hora_brl": 0,
        "valor_sugerido_brl": 0,
        "prazo_estimado_dias_uteis": 0,
        "case_utilizado": "",
        "perguntas_escopo": [],
        "proposta_texto": "",
    }
    validated = {**defaults, **result}
    for key in ("estimativa_horas", "valor_hora_brl", "valor_sugerido_brl", "prazo_estimado_dias_uteis"):
        try:
            validated[key] = max(0, int(round(float(validated.get(key) or 0))))
        except (TypeError, ValueError):
            validated[key] = 0
    if not isinstance(validated.get("perguntas_escopo"), list):
        validated["perguntas_escopo"] = []
    return validated


def _project_value(project: Any, key: str, default: Any = "") -> Any:
    if isinstance(project, dict):
        return project.get(key, default)
    return getattr(project, key, default)


def analyze_project(project: Any, profile: dict | None = None) -> dict[str, Any]:
    knowledge = load_knowledge()
    context = select_relevant_context(project)
    intelligence = build_proposal_intelligence(project)
    strategy: dict[str, Any] | None = None
    pricing: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    try:
        strategy = build_commercial_strategy(project, intelligence, knowledge)
    except Exception as exc:
        logger.exception("Falha ao montar estrategia comercial; seguindo sem ela: %s", exc)
    if strategy is not None:
        try:
            pricing = calculate_pricing(project, intelligence, strategy, knowledge)
        except Exception as exc:
            logger.exception("Falha ao calcular precificacao deterministica; seguindo com fallback da IA: %s", exc)
    if strategy is not None and pricing is not None:
        try:
            proposal = generate_proposal(project, intelligence, strategy, pricing, knowledge)
        except Exception as exc:
            logger.exception("Falha ao gerar proposta estruturada; seguindo com fallback da IA: %s", exc)

    payload = {
        "projeto": {
            "plataforma": _project_value(project, "platform"),
            "titulo": _project_value(project, "title"),
            "orcamento_informado": _project_value(project, "budget_text") or "não informado",
            "descricao": _project_value(project, "description") or "(descrição não capturada)",
            "skills_capturadas": _project_value(project, "skills", []) or [],
        },
        "inteligencia_proposta": intelligence,
        "contexto_profissional_selecionado": context,
    }
    if strategy is not None:
        payload["estrategia_comercial"] = strategy
    if pricing is not None:
        payload["precificacao"] = pricing
    if proposal is not None:
        payload["proposta_estruturada"] = proposal

    response = _client().chat.completions.create(
        model=MODEL,
        temperature=0.3,
        max_tokens=1400,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
        ],
    )

    raw = response.choices[0].message.content or ""
    try:
        result = _validate_result(_extract_json(raw))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        result = _validate_result(
            {
                "vale_a_pena": False,
                "motivo_curto": f"Falha ao interpretar resposta da IA: {exc}",
                "proposta_texto": raw,
            }
        )
    if pricing is not None:
        result["estimativa_horas"] = int(pricing["estimated_hours"])
        result["valor_hora_brl"] = int(round(float(pricing["hourly_rate_brl"])))
        result["valor_sugerido_brl"] = int(round(float(pricing["suggested_price_brl"])))
        if not result.get("motivo_curto") or result.get("motivo_curto") == "Resposta incompleta da IA":
            result["motivo_curto"] = pricing["pricing_reason"]
    if proposal is not None and pricing is not None:
        try:
            validation = validate_project_output(project, intelligence, strategy or {}, pricing, proposal)
            normalized = validation["normalized"]
            pricing = normalized["pricing"]
            proposal = normalized["proposal"]
        except Exception as exc:
            logger.exception("Falha ao validar saída do projeto; mantendo fluxo atual: %s", exc)
        result["proposta_texto"] = proposal["proposal_text"]
        result["estimativa_horas"] = int(float(pricing["estimated_hours"]))
        result["valor_sugerido_brl"] = int(round(float(pricing["suggested_price_brl"])))
        result["motivo_curto"] = pricing["pricing_reason"]
    return result
