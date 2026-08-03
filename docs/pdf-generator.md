# PDF Generator

## Objetivo

Gerar um PDF comercial compacto, premium e compatível com registros antigos.

## Entradas

Função pública:

```python
create_proposal_pdf(project, profile) -> bytes
```

O `project` pode conter campos estruturados diretamente, dentro de `structured_proposal`, dentro de `proposal`, ou apenas campos legados.

## Saídas

Bytes de PDF gerados em memória com:

```python
pdf.output(dest="S")
```

## Fluxo

1. Procura proposta estruturada no `project`.
2. Se não encontrar, reconstrói localmente com:
   - Proposal Intelligence;
   - Commercial Strategy;
   - Pricing Engine;
   - Proposal Generator.
3. Se a reconstrução falhar, usa fallback legado.
4. Sanitiza texto apenas no momento de escrever no PDF.
5. Renderiza seções dinâmicas somente quando há conteúdo.
6. Controla paginação manualmente com `ensure_space`.
7. Gera assinatura compacta no final do conteúdo.

## Fallback

O fallback legado usa:

- `title`;
- `proposal_text`;
- `suggested_price_brl`;
- `estimated_hours`;
- dados do perfil.

## Exemplo

```python
from pdf_generator import create_proposal_pdf

pdf_bytes = create_proposal_pdf(project, profile)
assert pdf_bytes.startswith(b"%PDF")
```
