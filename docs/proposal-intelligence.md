# Proposal Intelligence

## Objetivo

Interpretar o projeto antes da proposta e gerar um contexto estruturado para as próximas camadas.

## Entradas

Projeto normalizado:

```json
{
  "id": "...",
  "platform": "...",
  "title": "...",
  "description": "...",
  "skills": [],
  "budget_text": "...",
  "url": "..."
}
```

Também usa a base carregada por `knowledge_engine.load_knowledge()`.

## Saídas

Retorna um dicionário com:

- `category`
- `problem_summary`
- `client_goal`
- `complexity`
- `scope_confidence`
- `relevant_services`
- `relevant_technologies`
- `relevant_cases`
- `relevant_experience`
- `deliverables`
- `risks`
- `clarifying_questions`
- `timeline`
- `pricing_context`
- `commercial_arguments`

## Fluxo

1. Normaliza título, descrição e skills.
2. Aplica regras de categoria.
3. Seleciona tecnologias citadas no projeto.
4. Seleciona serviços aderentes.
5. Seleciona no máximo dois cases relevantes.
6. Seleciona experiências relacionadas.
7. Calcula complexidade.
8. Detecta riscos.
9. Gera perguntas de escopo.
10. Monta contexto para precificação.

## Fallback

Quando poucos sinais são encontrados, a camada retorna categoria vazia ou baixa confiança, mas preserva a estrutura esperada. Isso permite que as próximas camadas continuem funcionando.

## Exemplo

Entrada:

```json
{
  "title": "Dashboard Power BI para vendas",
  "description": "Preciso de indicadores de faturamento, vendedor e atualização simples.",
  "skills": ["Power BI", "DAX"]
}
```

Saída resumida:

```json
{
  "category": "Power BI",
  "complexity": "medium",
  "relevant_technologies": ["Power BI", "DAX"],
  "risks": [],
  "timeline": ["Levantamento", "Desenvolvimento", "Testes", "Entrega"]
}
```
