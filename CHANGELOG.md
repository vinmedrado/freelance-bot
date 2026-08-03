# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.

## 2.0.0 - 2026-08-03

### Principais mudanças

- Adicionada camada `proposal_intelligence.py` para entendimento determinístico do projeto.
- Adicionada camada `commercial_strategy.py` para estratégia comercial.
- Adicionado `pricing_engine.py` como fonte principal de preço e horas.
- Adicionado `proposal_generator_v2.py` para proposta estruturada.
- Refatorado `pdf_generator.py` para PDF comercial compacto, dinâmico e sem páginas vazias.
- Evoluído `webapp.py` com view model estruturado, detalhe do projeto e API de proposta.
- Adicionados testes automatizados para inteligência, estratégia, precificação, proposta, PDF e dashboard.
- Organizada base de conhecimento em YAML.
- Mantida compatibilidade com banco SQLite, rotas existentes e campos legados.
