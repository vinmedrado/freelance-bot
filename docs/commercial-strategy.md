# Commercial Strategy

## Objetivo

Transformar o diagnóstico técnico em uma estratégia comercial objetiva e verdadeira.

## Entradas

- projeto normalizado;
- resultado de `build_proposal_intelligence`;
- base de conhecimento carregada.

## Saídas

Retorna:

- `positioning`
- `value_proposition`
- `client_priorities`
- `proposal_angle`
- `proof_points`
- `relevant_cases`
- `relevant_experience`
- `objections`
- `responses_to_objections`
- `recommended_tone`
- `cta`
- `sections_emphasis`
- `claims_to_avoid`

## Fluxo

1. Lê categoria e riscos da inteligência.
2. Escolhe posicionamento por categoria.
3. Define proposta de valor.
4. Seleciona prioridades prováveis do cliente.
5. Escolhe ângulo comercial principal.
6. Seleciona provas e experiências.
7. Reaproveita cases relevantes da inteligência.
8. Antecipa objeções e respostas.
9. Define tom, CTA e seções prioritárias.
10. Lista afirmações que devem ser evitadas.

## Fallback

Quando a categoria não é clara, usa posicionamento consultivo genérico para soluções de dados e automação. Se não houver objeções, considera manutenção como objeção padrão.

## Exemplo

Para Power BI:

```json
{
  "positioning": "analista de dados com experiencia em dashboards e Power BI",
  "proposal_angle": "clareza para decisao",
  "recommended_tone": "consultivo e executivo"
}
```
