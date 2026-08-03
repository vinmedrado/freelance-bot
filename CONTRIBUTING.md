# Contributing

Obrigado pelo interesse em contribuir.

## Como executar localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chrome
copy .env.example .env
python validate_setup.py
pytest -q
```

No macOS/Linux:

```bash
source .venv/bin/activate
cp .env.example .env
```

## Como contribuir

1. Abra uma issue descrevendo o problema ou melhoria.
2. Crie uma branch pequena e focada.
3. Preserve compatibilidade com banco, rotas e campos legados.
4. Adicione ou ajuste testes quando alterar comportamento.
5. Rode validações antes de abrir o Pull Request.

## Como reportar bugs

Inclua:

- sistema operacional;
- versão do Python;
- comando executado;
- traceback completo;
- plataforma afetada;
- se o Chrome estava aberto com `--remote-debugging-port=9222`;
- trecho do anúncio, quando relevante e sem dados sensíveis.

## Pull Requests

Antes de abrir um PR, execute:

```bash
pytest -q
python validate_setup.py
python -m py_compile ai_engine.py commercial_strategy.py db.py knowledge_engine.py main.py matcher.py pdf_generator.py pricing_engine.py proposal_generator_v2.py proposal_intelligence.py validate_setup.py webapp.py
```

Evite misturar refatoração, documentação e mudança de comportamento no mesmo PR.
