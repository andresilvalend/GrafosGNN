# Sessão 2026-03-20 — Sync do repo, PLANO.md e CLAUDE.md

## O que foi feito
- Comparado arquivos locais (Downloads/) com o que estava no GitHub
- Identificado 13 arquivos não commitados: BCCS paper v4/v5, docs teoria, scripts, validate_docx.py
- Atualizado PLANO.md com resultados nb09–nb13 (não estavam documentados)
- Criado CLAUDE.md com regras de sessão, mapa de CSVs, definições de métricas
- Adicionado regra de log de sessão obrigatório (esta pasta sessions/)
- Pushed tudo para origin/main (27 commits à frente estavam pendentes)

## Decisões tomadas
- **CLAUDE.md na raiz**: lido automaticamente pelo Claude em qualquer sessão nova — garante que as regras de validação sempre se aplicam sem precisar repetir no prompt
- **Pasta sessions/**: log de cada análise commitado no git para não perder contexto entre sessões
- **Template de sessão fixo**: campos obrigatórios (decisões, resultados, próximos passos) para reconstrução do raciocínio

## Estado do projeto nesta sessão
- Paper mais recente: `BCCS_paper_v5.1.docx`
- Algoritmo: HGS (WCC → Leiden → Capping B=100)
- Problema: BCCS-P (partição V_k, budget sobre presented edges)
- Experimentos concluídos: nb04–nb13
- Avaliação: ~95% pronto para ICDM 2026

## Arquivos alterados nesta sessão
- `PLANO.md` — atualizado com nb09–nb13, HGS nome final, assessment 95%
- `CLAUDE.md` — criado (regras de sessão, mapa CSVs, métricas, workflow)
- `sessions/` — pasta criada com template de log
- `docs/bccs_theory_v4.md` — teoria BCCS v4 (commitado)
- `docs/bccs_theory_v5.md` — teoria v5 com provas formais (commitado)
- `docs/v4_formal_decisions.md` — decisões formais paper v4+ (commitado)
- `BCCS_paper_v4.docx` → `v4.4.docx` — versões paper (commitado)
- `BCCS_paper_v5.docx`, `v5.1.docx` — versões paper (commitado)
- `BTCS_paper_v3.docx` — versão paper (commitado)
- `validate_docx.py` — script validação .docx (commitado)

## Próximos passos
- [ ] Finalizar escrita paper v5 (`BCCS_paper_v5.1.docx` → `v5.2.docx`)
- [ ] PaySim yield@100 (30min, +1 linha na tabela de resultados)
- [ ] Submeter ICDM 2026
