# Decision Log

Este documento registra as principais decisões arquiteturais do projeto.

## Proposal Intelligence

Foi criada uma camada determinística antes da proposta para evitar que a IA interpretasse sozinha o projeto. A camada classifica categoria, complexidade, riscos, serviços, tecnologias, cases, entregáveis e perguntas.

Decisão: separar entendimento técnico de redação.

Motivo: melhorar consistência, reduzir alucinação e permitir uso dos mesmos dados no preço, PDF e dashboard.

## Commercial Strategy

A estratégia comercial foi separada da inteligência técnica para transformar diagnóstico em comunicação. Ela define posicionamento, proposta de valor, prioridades do cliente, provas, objeções, respostas, tom e CTA.

Decisão: criar uma camada comercial determinística.

Motivo: evitar propostas genéricas e impedir que a IA escolha argumentos sem aderência ao projeto.

## Pricing Engine

O motor de preço foi criado para tirar da IA a decisão principal de preço e horas. Ele usa faixas configuradas, complexidade, riscos, entregáveis, orçamento informado, tecnologias e premissas.

Decisão: preço principal deve ser determinístico.

Motivo: precificação precisa ser auditável, repetível e compatível com regras comerciais.

## Proposal Generator

O gerador de proposta foi criado para substituir texto corrido genérico por uma estrutura comercial reutilizável. Ele produz headline, resumo, entendimento, desafios, solução, entregáveis, método, cronograma, tecnologias, cases, investimento, perguntas, proposta completa e proposta curta.

Decisão: proposta deve nascer estruturada.

Motivo: a mesma proposta alimenta dashboard, cópia para plataformas e PDF.

## PDF Generator

O PDF foi refatorado para consumir a proposta estruturada e evitar páginas vazias, blocos sem conteúdo e excesso de texto. Ele mantém fallback legado para registros antigos.

Decisão: PDF deve ser uma camada de apresentação, não uma nova fonte de conteúdo comercial.

Motivo: preservar preço, horas e proposta gerados pelo pipeline.

## Dashboard

O dashboard foi evoluído para mostrar diagnóstico, preço, proposta curta, proposta completa, cases, PDF e status. Como o banco ainda guarda campos legados, o dashboard reconstrói a estrutura determinística quando necessário.

Decisão: não alterar schema para exibir dados estruturados.

Motivo: preservar compatibilidade com banco, rotas, scrapers e registros existentes.
