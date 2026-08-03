# Proposal Generator

## Objetivo

Gerar uma proposta estruturada, natural e reutilizável no dashboard, em plataformas freelance e no PDF.

## Entradas

- projeto normalizado;
- intelligence;
- commercial strategy;
- pricing;
- knowledge;
- cliente opcional de refinamento textual.

## Saídas

Retorna:

- `headline`
- `executive_summary`
- `understanding`
- `identified_challenges`
- `proposed_solution`
- `deliverables`
- `work_method`
- `timeline`
- `technologies`
- `relevant_cases`
- `proof_points`
- `investment_summary`
- `assumptions`
- `clarifying_questions`
- `next_step`
- `proposal_text`
- `short_proposal_text`

## Fluxo

1. Define headline por categoria.
2. Gera resumo executivo.
3. Descreve entendimento do projeto.
4. Lista desafios suportados por sinais do projeto.
5. Gera solução proposta por categoria.
6. Seleciona entregáveis específicos.
7. Monta método e cronograma.
8. Seleciona tecnologias relevantes.
9. Reaproveita cases e provas da estratégia.
10. Escreve investimento com preço e horas do Pricing Engine.
11. Monta proposta completa e curta.

## Fallback

Se não houver cliente de IA, a proposta é 100% determinística. Se houver refinamento opcional, campos factuais como preço, horas, cases, tecnologias e entregáveis não devem ser alterados.

## Exemplo

```json
{
  "headline": "Dashboard Power BI para análise clara dos indicadores",
  "deliverables": [
    "Dashboard Power BI funcional",
    "Modelo de dados organizado",
    "Indicadores validados"
  ],
  "short_proposal_text": "Olá! O objetivo é transformar os dados..."
}
```
