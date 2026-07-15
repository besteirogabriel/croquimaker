# Auditoria Curta V2

Data: 2026-06-25.

## Estrutura Atual Confirmada

- Aplicacao Flask local em `croqui_engine/app/` com login, dashboard, upload, detalhe, revisao visual e downloads.
- Pipeline V1 em `croqui_engine/core/pipeline.py`, com extracao PyMuPDF, parsers deterministas, grafo, validacao e geracao PDF/PNG/XLS.
- Modelos V1 em `croqui_engine/core/models.py`.
- Catalogo heuristico atual em `croqui_engine/symbols/default_rge_heuristic.yaml`.
- Geradores atuais em `croqui_engine/generators/`.
- Pasta legada isolada em `projeto_legado/`.
- Documentacao de limitacoes em `docs/O_QUE_O_SISTEMA_NAO_CONSEGUE_FAZER.md`.

## Corpus Confirmado

- Pasta `CROQUI IA/` encontrada na raiz.
- 155 diretorios de caso.
- 308 arquivos PDF.
- 155 arquivos `.xls`.
- Estrutura predominante por caso: projeto bruto PDF, croqui final PDF e croqui final XLS.

## Direcao de Implementacao

A V1 sera preservada como fallback. A V2 entra como uma camada adicional baseada em:

- registry do corpus aprovado;
- ground truth extraido de PDF/XLS final;
- catalogo oficial inicial extraido da aba `Simbologia`;
- benchmark visual/tecnico;
- relatorios e UI administrativa para auditoria.

## Limite Honesto Desta Rodada

A primeira entrega V2 cria a base objetiva de comparacao contra corpus. Ela ainda nao resolve toda a fidelidade de renderizacao/topologia, mas passa a medir divergencias reais contra o croqui aprovado e prepara os proximos ciclos de calibracao.
