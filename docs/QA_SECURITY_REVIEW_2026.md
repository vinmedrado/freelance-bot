# QA e limites da validação — 11/11/2026

**Escopo:** GitHub Actions com token somente leitura, Python 3.11, dependências de desenvolvimento e testes sem chave Groq nem acesso às contas das plataformas.

## Evidências
- **61 testes automatizados aprovados**: consistência de precificação, propostas, filtros, validação de projeto e geração de documentos.
- O workflow compila os arquivos Python e executa pytest.
- A demonstração pública permanece estática e usa dados ilustrativos; não acessa contas de freelancers.

## Segurança e limitações
- A configuração de credenciais é documentada em `.env.example`, enquanto `.env` e bancos SQLite locais são ignorados no Git.
- Não houve verificação funcional das sessões reais de navegadores, permissões de plataformas, bloqueios anti-bot ou execução de chamadas Groq. Não se deve inserir tokens no código-fonte.
- A suíte não prova ausência de vulnerabilidades em dependências com versões mínimas abertas; atualizações devem ser auditadas separadamente.
- Propostas são geradas para revisão humana; o projeto não promete envio automático.
