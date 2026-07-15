# CroquiMaker V1 — Output-First Codex Pack

Este pacote substitui a orientação anterior centrada em `CroquiScene` como objetivo do produto.

A diretriz correta da V1 é **output-first**:

- o objetivo principal é gerar **PDF e XLSX finais 100% corretos no padrão Jobel/RGE**;
- qualquer modelo intermediário só é válido se produzir output final fiel;
- o editor online existe para corrigir o output, manter paridade visual e permitir exportação final correta;
- os 155 pares reais `projeto + croqui ideal PDF + croqui ideal XLSX` são base de homologação, regressão e calibração;
- não aceitar geração que “parece plausível” mas não entrega o croqui final correto.

## Ordem recomendada de execução no Codex

1. `prompts/00_DIRETRIZ_MESTRE_OUTPUT_FIRST.md`
2. `prompts/01_MAPEAMENTO_ENGINE_ATUAL_E_CONTRATO_DE_OUTPUT.md`
3. `prompts/02_EQUIPAMENTO_PRINCIPAL_E_FOCO_TECNICO.md`
4. `prompts/03_RENDERIZACAO_FIEL_PDF_XLSX.md`
5. `prompts/04_EDITOR_ONLINE_COM_PARIDADE_DE_OUTPUT.md`
6. `prompts/05_CORPUS_155_HOMOLOGACAO_REGRESSAO.md`
7. `prompts/06_VALIDACAO_BLOQUEANTE_E_SCORE_DE_ACEITE.md`
8. `prompts/07_MIGRACAO_INCREMENTAL_SEM_REESCRITA_TOTAL.md`
9. `prompts/08_CRITERIOS_DE_PRONTO_V1.md`

## AGENTS.md

Os arquivos em `AGENTS/` devem ser copiados para o repositório conforme a estrutura indicada:

- `AGENTS/root_AGENTS.md` → `AGENTS.md`
- `AGENTS/croqui_engine_AGENTS.md` → `croqui_engine/AGENTS.md`
- `AGENTS/frontend_AGENTS.md` → `frontend/AGENTS.md` quando o editor React existir
- `AGENTS/exporters_AGENTS.md` → `croqui_engine/generators/AGENTS.md`
- `AGENTS/tests_AGENTS.md` → `tests/AGENTS.md`

## Tese técnica da V1

A V1 não deve ser vendida como “o sistema que interpreta tudo sozinho”. A V1 deve ser o sistema que entrega um fluxo industrial:

`projeto bruto → rascunho técnico calibrado → correção visual assistida → PDF/XLSX final homologável`.

A geração automática pode começar com uma meta operacional de 70% de confiabilidade, mas a entrega final só passa quando o PDF/XLSX exportado atende aos critérios de output. O editor não é acessório; ele é parte do mecanismo de garantia de qualidade do output.
