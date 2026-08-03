# Arquitetura

O Freelance Bot é organizado em camadas independentes. A maior parte das decisões comerciais é determinística, e a IA é tratada como apoio textual dentro do fluxo principal.

## Camadas

```text
Entrada das plataformas
  ↓
Scrapers
  ↓
Persistência e deduplicação
  ↓
Matching
  ↓
Inteligência da proposta
  ↓
Estratégia comercial
  ↓
Precificação
  ↓
Geração da proposta
  ↓
PDF e dashboard
```

## Responsabilidades

### Scrapers

Os scrapers em `scrapers/` usam Playwright e Chrome DevTools Protocol para reaproveitar uma sessão autenticada do Chrome. Eles retornam projetos normalizados com campos como `id`, `platform`, `title`, `description`, `skills`, `budget_text` e `url`.

### Persistência

`db.py` usa SQLite para guardar projetos já vistos e resultados de proposta. O schema atual armazena campos legados como `proposal_text`, `suggested_price_brl`, `estimated_hours`, `ai_reasoning` e `status`.

### Matching

`matcher.py` calcula score de aderência usando perfil e palavras-chave. Essa etapa filtra oportunidades antes de gastar processamento com geração de proposta.

### Knowledge Engine

`knowledge_engine.py` carrega arquivos YAML em `knowledge/` e monta um contexto profissional seletivo. A base inclui identidade, experiência, serviços, especialidades, tecnologias, cases, negociação, proposta, estilo de escrita e precificação.

### Proposal Intelligence

`proposal_intelligence.py` interpreta o projeto de forma determinística. Ele classifica categoria, complexidade, tecnologias, serviços, riscos, entregáveis, perguntas e cases.

### Commercial Strategy

`commercial_strategy.py` transforma o diagnóstico técnico em estratégia comercial: posicionamento, proposta de valor, objeções, provas, tom, CTA e seções prioritárias.

### Pricing Engine

`pricing_engine.py` calcula preço e horas sem depender da IA. O resultado inclui tipo de projeto, complexidade, horas, valor/hora, faixa, ajustes, confiança e premissas.

### Proposal Generator

`proposal_generator_v2.py` gera uma proposta estruturada com headline, resumo, entendimento, solução, entregáveis, cronograma, tecnologias, cases, investimento, perguntas, texto completo e texto curto.

### AI Engine

`ai_engine.py` integra a Groq ao fluxo de análise. Quando o motor de preço e o gerador estruturado funcionam, preço e horas do resultado final são sobrescritos pelos valores determinísticos.

### PDF Generator

`pdf_generator.py` gera o PDF em memória com FPDF. Ele usa proposta estruturada quando disponível, reconstrói determinísticamente quando necessário e cai para campos legados se algo falhar.

### Dashboard

`webapp.py` expõe dashboard Flask, detalhe do projeto, APIs de proposta, atualização de status, download de PDF e controle de varredura.

## Dependências principais

- `main.py` depende de scrapers, matcher, AI engine e banco.
- `ai_engine.py` depende de knowledge, proposal intelligence, commercial strategy, pricing engine e proposal generator.
- `webapp.py` reutiliza as camadas determinísticas para reconstruir visão estruturada sem chamar Groq.
- `pdf_generator.py` pode funcionar com dados estruturados, reconstrução local ou fallback legado.

## Fluxo de dados

1. Scraper coleta um projeto normalizado.
2. Banco evita processar projeto duplicado.
3. Matcher calcula score.
4. Projetos aderentes passam por análise.
5. Intelligence gera contexto técnico.
6. Strategy gera direção comercial.
7. Pricing calcula preço principal.
8. Proposal Generator monta proposta estruturada.
9. AI Engine preserva preço/horas determinísticos e salva campos legados.
10. Dashboard reconstrói a estrutura para visualização.
11. PDF usa a mesma estrutura quando disponível.

## Fallbacks

- Se estratégia comercial falhar, o fluxo de IA segue com inteligência técnica.
- Se precificação falhar, o fluxo anterior da IA continua como fallback.
- Se geração estruturada falhar, o fluxo anterior de proposta é preservado.
- Se PDF não encontrar proposta estruturada, ele reconstrói localmente.
- Se reconstrução do dashboard falhar, a tela usa `proposal_text`, preço e horas legados.
