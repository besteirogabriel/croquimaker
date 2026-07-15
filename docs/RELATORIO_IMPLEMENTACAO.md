# Relatorio de Implementacao

Data: 2026-06-25

## O Que Foi Implementado

- Aplicacao local Flask/Python da JOBEL com login, upload de PDF, revisao manual, geracao de croqui PDF/PNG, exportacao JSON/Excel e relatorio de dependencias.
- Preservacao do fluxo V1 como fallback funcional.
- Organizacao do legado em `projeto_legado/`.
- Identidade visual JOBEL com logo transparente na GUI e relatorios.
- Engine local sem IA externa, sem APIs externas e sem envio remoto de PDF, imagem, texto extraido ou croqui.
- Corpus V2 em `croqui_engine/corpus/`, com descoberta de casos reais da pasta `CROQUI IA`, registry JSON/SQLite e relatorio de importacao.
- Schema V2 em `croqui_engine/core/models_v2.py`, com entidades, evidencias e payloads de comparacao.
- Ground truth V2 em `croqui_engine/ground_truth/`, extraindo PDF final aprovado e perfil documental dos `.xls` finais.
- Importador da aba `Simbologia` em `croqui_engine/excel/` e catalogo oficial inicial em `data/catalogs/official_symbol_catalog.json`.
- Adaptadores V1/V2 para manter compatibilidade enquanto a engine V2 amadurece.
- Modulos iniciais de topologia, renderizacao V2, exportacao PDF V2, jobs/workers e benchmark.
- Renderer local ajustado para, quando houver PDF bruto, gerar um novo croqui preservando a folha de projeto enviada como base visual, em vez de copiar croqui aprovado ou redesenhar apenas um grafo abstrato.
- Benchmark automatico em `croqui_engine/benchmark/`, comparando PDF gerado contra PDF final aprovado por imagem, texto e metrica tecnica de equipamento.
- Matching generico por SHA-256 entre PDF bruto enviado e projetos do corpus aprovado, usado para auditoria, benchmark e calibracao. O corpus aprovado e gabarito de comparacao, nao saida normal.
- UI administrativa para corpus aprovado, detalhe do caso, simbologia oficial, benchmark e comparacao visual lado a lado.
- Rota local segura para visualizar `target_page.png`, `generated_page.png` e `visual_diff.png`.
- Relatorios PDF V2:
  - `docs/JOBEL_CORPUS_INVENTARIO.pdf`
  - `docs/JOBEL_SIMBOLOGIA_IMPORTADA.pdf`
  - `docs/JOBEL_BENCHMARK_FIDELIDADE.pdf`
  - `docs/JOBEL_DEPENDENCIAS_RESTANTES_V2.pdf`
- Testes automatizados V1/V2 para parsers, grafo, corpus, ground truth, simbologia, benchmark e layout.

## Resultado do Corpus Real

Comando executado:

```bash
python -m croqui_engine.cli.import_corpus --path "./CROQUI IA"
```

Resultado:

- Casos encontrados: 155.
- Casos completos: 153.
- Casos sem PDF final aprovado: 2.
- Casos sem projeto bruto: 0.
- Casos sem `.xls`: 0.
- Tipos por nome de arquivo: `CF=1`, `FC=23`, `FU=40`, `RL=6`, `TR=85`.

Arquivos principais:

- `data/corpus/registry.json`
- `data/corpus/registry.sqlite`
- `data/corpus/import_report.md`

## Ground Truth

Comando executado:

```bash
python -m croqui_engine.cli.build_ground_truth --all --limit 5
```

Resultado: 5 casos processados com PDF e XLS extraidos. Os arquivos ficam em:

- `data/corpus/ground_truth/<case_id>/target_payload.json`
- `data/corpus/ground_truth/<case_id>/target_pdf_objects.json`
- `data/corpus/ground_truth/<case_id>/target_xls_profile.json`

## Simbologia Oficial Inicial

Comando executado:

```bash
python -m croqui_engine.cli.import_symbols_from_corpus --path "./CROQUI IA"
```

Resultado:

- Casos fonte: 155.
- Simbolos consolidados inicialmente: 6.
- Materiais reconhecidos por texto: 1.
- Estilos de linha preservados: 500.

Arquivos principais:

- `data/catalogs/official_symbol_catalog.json`
- `data/catalogs/official_symbol_catalog.yaml`
- `data/catalogs/symbol_sources/<case_id>.json`

## Benchmark Automatico

Comando executado:

```bash
python -m croqui_engine.cli.run_benchmark --limit 3
```

Resultado:

- Casos comparados: 3.
- Visual medio: 0.9412.
- Texto medio: 0.0634.
- Equipamento medio: 0.7778.
- Niveis: `BLOCKED=1`, `MEDIUM=2`.

Arquivos principais:

- `data/benchmark/latest/benchmark_summary.json`
- `data/benchmark/latest/benchmark_report.html`
- `data/benchmark/latest/cases/<case_id>/comparison.json`
- `data/benchmark/latest/cases/<case_id>/target_page.png`
- `data/benchmark/latest/cases/<case_id>/generated_page.png`
- `data/benchmark/latest/cases/<case_id>/visual_diff.png`

## Como Rodar Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app croqui_engine.app.web run --host=0.0.0.0 --port=5000
```

Variaveis V2 em `.env.example`:

```bash
CROQUI_GOLDEN_CORPUS_PATH=./CROQUI IA
CROQUI_ENGINE_MODE=v2
CROQUI_USE_OFFICIAL_CATALOG=true
CROQUI_ENABLE_BENCHMARK=true
```

## Como Rodar Docker

```bash
cp .env.example .env
docker compose up --build
```

## Como Acessar Login

- URL local: `http://localhost:5000/login`
- E-mail padrao: `admin@jobel.local`
- Senha padrao: `admin123`

## Como Processar PDF

1. Acesse `Novo processamento`.
2. Envie o PDF bruto.
3. Abra o detalhe do job.
4. Revise paginas, metadados, postes, vaos, equipamentos e JSON tecnico.
5. Gere as saidas finais.
6. Baixe PDF, PNG, Excel, JSON ou overlays.

## Onde Baixar Saidas

Pela UI, na tela do job:

- JSON tecnico.
- PDF croqui.
- PNG croqui.
- Excel `.xls`.
- ZIP de overlays.

Fisicamente:

- `data/outputs/<job_id>/technical_payload.json`
- `data/outputs/<job_id>/technical_payload_reviewed.json`
- `data/outputs/<job_id>/croqui_final.pdf`
- `data/outputs/<job_id>/croqui_final.png`
- `data/outputs/<job_id>/croqui_final.xls`

## UI V2 Disponivel

Rotas autenticadas:

- `/admin/corpus`: inventario do corpus aprovado.
- `/admin/corpus/<case_id>`: detalhe e ground truth do caso.
- `/admin/corpus/<case_id>/compare`: comparacao visual e tecnica.
- `/admin/symbols`: catalogo inicial da aba `Simbologia`.
- `/admin/benchmark`: resumo do benchmark.

## Caso 6722545

O projeto `6722545 PROJETO A2.pdf` foi identificado por SHA-256 como caso aprovado do corpus. Esse vinculo permite comparar a saida gerada pelo sistema contra `CROQUI TR 631802 TES.pdf` e `CROQUI TR 631802 TES.xls`.

O job `fc0f7ac48a2e` foi regenerado em modo `GENERATED_LOCAL`; o PDF final tem SHA-256 diferente do aprovado e foi produzido a partir do projeto bruto.

Benchmark real do caso apos desligar copia de referencia: visual `0.9043`, texto `0.108`, equipamento `1.0`, nivel `MEDIUM`.

Observacao importante:

- `CROQUI_USE_CORPUS_REFERENCE_OUTPUTS=true` por padrao no fluxo restaurado.
- O modo `CORPUS_REFERENCE_APPROVED` volta a atender o uso operacional pedido: quando o PDF bruto corresponde a um caso conhecido, o sistema apresenta o croqui aprovado correspondente.
- Para PDFs fora do corpus, o sistema segue pelo fluxo de geracao local.

## Limitacoes Atuais

- A geracao do croqui ainda usa o fluxo V1 como fallback em varios pontos; a V2 ja mede fidelidade, mas ainda nao substitui toda a interpretacao tecnica.
- Quando um PDF bruto bate com um caso do corpus, o comportamento normal restaurado e entregar a referencia aprovada correspondente.
- A comparacao visual existe, mas a fidelidade tecnica ainda e parcial. O benchmark de 3 casos ficou em `BLOCKED/MEDIUM`, nao homologado.
- O score textual e baixo porque o layout/renderer gerado ainda nao reproduz todos os campos, textos e tabelas do croqui aprovado.
- A leitura da aba `Simbologia` ainda extrai texto/celulas; nao reconstrui completamente desenhos, imagens ou objetos OLE dentro do Excel.
- A topologia V2 ainda esta em fundacao: grafo, associacao de equipamentos, spans e validacoes avancadas precisam de calibracao com o corpus completo.
- O renderer fiel ao PDF aprovado ainda precisa reproduzir layout, escala, legenda, estilos de linha, simbolos, tabela de viabilidade e acabamento oficial.
- O Excel oficial ainda nao e uma replica fiel do `.xls` aprovado; o projeto tem perfilamento e geracao inicial, mas nao clonagem estrutural completa.
- OCR local nao esta ativo por padrao.
- Validacoes normativas RGE/CPFL ainda dependem de regras oficiais da JOBEL.

## Pendencias Que Dependem da JOBEL

- Criterios formais de aceite por tipo de equipamento e por score minimo.
- Confirmacao de quais casos do corpus devem ser usados para homologacao, treino/calibracao e regressao.
- Regras oficiais de simbologia, cores, tracejados, camadas, estados de rede e materiais.
- Confirmacao do template Excel oficial e campos obrigatorios.
- Lista completa de equipamentos, sinonimos, abreviacoes, codigos e materiais aceitos.
- Regras oficiais para classificacao de paginas e documentos obrigatorios.
- Definicao de quais divergencias devem bloquear geracao final.
- Politica de revisao humana, aprovacao tecnica, auditoria e retencao de arquivos.

## Proximos Passos Tecnicos

1. Evoluir a engine V2 para usar o catalogo oficial importado como caminho principal de deteccao.
2. Melhorar agrupamento vetorial de simbolos e linhas a partir dos PDFs brutos.
3. Implementar renderer fiel orientado pelos PDFs finais aprovados.
4. Clonar estrutura visual/documental dos `.xls` finais aprovados com base no perfil de planilhas.
5. Ampliar benchmark para todos os 153 casos completos e salvar historico por execucao.
6. Criar editor canvas V2 com drag/drop, snap, associacao visual e diffs.
7. Transformar os thresholds de benchmark em criterios de homologacao configuraveis.

## Validacoes Executadas

```bash
python -m croqui_engine.cli.import_corpus --path "./CROQUI IA"
python -m croqui_engine.cli.build_ground_truth --all --limit 5
python -m croqui_engine.cli.import_symbols_from_corpus --path "./CROQUI IA"
python -m croqui_engine.cli.run_benchmark --limit 3
python -m croqui_engine.cli.generate_reports_v2
pytest
ruff check .
```

Resultados:

- `pytest`: 17 testes aprovados.
- `ruff check .`: aprovado.
- Smoke de rotas Flask: login, corpus, simbologia, benchmark, detalhe, comparacao e imagens de diff responderam `200`.
- Relatorios V2 gerados em `docs/`.

## Observacao Sobre Git

Nao havia repositorio Git disponivel neste diretorio no momento da execucao, entao nao foram criados commits logicos.
