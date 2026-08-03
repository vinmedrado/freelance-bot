# Pricing Engine

## Objetivo

Calcular preço e horas de forma determinística, explicável e segura.

## Entradas

- projeto normalizado;
- intelligence;
- strategy;
- knowledge, especialmente `knowledge/pricing.yaml`.

## Saídas

Retorna:

- `project_type`
- `complexity`
- `estimated_hours`
- `hourly_rate_brl`
- `base_price_brl`
- `adjustments`
- `suggested_price_brl`
- `minimum_price_brl`
- `maximum_price_brl`
- `confidence`
- `pricing_reason`
- `assumptions`
- `requires_scope_validation`

## Fluxo

1. Mapeia categoria/serviço para tipo de projeto.
2. Detecta fatores como integração, autenticação, deploy, frontend, backend e urgência.
3. Estima horas dentro de faixas internas por tipo e complexidade.
4. Calcula valor/hora com limites de `pricing.yaml`.
5. Aplica ajustes explicáveis sem duplicar fatores equivalentes.
6. Limita multiplicador combinado por complexidade.
7. Arredonda preço em múltiplos comerciais.
8. Respeita mínimo e máximo por tipo.
9. Analisa orçamento informado sem forçar redução.
10. Calcula confiança e necessidade de validação de escopo.

## Fallback

Quando nenhum tipo é identificado, usa fallback seguro em `automacao_python`, mantendo limites comerciais configurados.

## Exemplo

```json
{
  "project_type": "dashboard_power_bi",
  "complexity": "medium",
  "estimated_hours": 27,
  "suggested_price_brl": 2400.0,
  "requires_scope_validation": false
}
```
