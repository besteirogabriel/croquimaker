# Fase 5 — Corpus de 155 casos como homologação e regressão

Objetivo: usar os 155 exemplos reais para medir e melhorar fidelidade de output, sem depender de treinamento opaco.

Cada caso possui:

- projeto bruto PDF;
- croqui ideal PDF;
- croqui ideal XLSX/XLS.

A V1 deve usar esses casos como prova funcional, benchmark e regressão.

## Tarefa 1 — Importador de corpus

Auditar e ampliar:

- `croqui_engine/cli/import_corpus.py`
- `croqui_engine/corpus/discovery.py`
- `croqui_engine/corpus/registry.py`
- `croqui_engine/corpus/storage.py`
- `croqui_engine/ground_truth/target_builder.py`
- `croqui_engine/ground_truth/pdf_target_extractor.py`
- `croqui_engine/ground_truth/xls_target_extractor.py`

Criar comando robusto:

```bash
python -m croqui_engine.cli.import_corpus --input data/examples --output data/corpus
```

Para cada caso, gerar:

```text
case_id/
  project.pdf
  target.pdf
  target.xlsx ou target.xls
  output_contract.json
  target_pdf_profile.json
  target_xlsx_profile.json
  visual_signature.json
  required_codes.json
  validation_rules.json
```

## Tarefa 2 — Extrair contrato a partir do target

O importador deve extrair:

- equipamento esperado;
- tipo de equipamento;
- código do equipamento;
- município;
- departamento;
- data;
- responsável;
- códigos visíveis no target PDF;
- códigos do target XLSX;
- posições aproximadas de cabeçalho e desenho;
- assinatura visual do croqui ideal;
- template XLSX associado.

Se PDF ideal e XLSX ideal divergirem em campo crítico, registrar warning ou bloquear o caso até revisão manual.

## Tarefa 3 — Benchmark de output

Criar ou ajustar runner para executar:

```bash
python -m croqui_engine.cli.run_benchmark --corpus data/corpus --mode output-fidelity
```

Métricas obrigatórias:

### Bloqueantes

- equipamento principal correto;
- cabeçalho PDF correto;
- cabeçalho XLSX correto;
- PDF e XLSX consistentes;
- foco primário correto;
- output final não dominado por código/equipamento proibido.

### De qualidade

- códigos esperados presentes;
- elementos secundários coerentes;
- sem códigos indevidos dominantes;
- similaridade visual com target PDF;
- similaridade de estrutura com target XLSX;
- tabela de viabilidade coerente;
- legenda coerente.

## Tarefa 4 — Relatório executivo

Gerar relatório:

`reports/output_fidelity_report.html`

Com:

- taxa de aprovação final;
- taxa de bloqueios críticos;
- top 20 divergências;
- casos em que edição manual seria necessária;
- casos com PDF correto e XLSX divergente;
- casos com XLSX correto e PDF divergente;
- score visual por caso;
- score técnico por caso.

## Tarefa 5 — Golden cases

Selecionar pelo menos 10 casos representativos como golden tests:

- TR;
- FU;
- FC;
- RL;
- rede com ramal;
- rede com transformador próximo;
- caso com múltiplos equipamentos candidatos;
- caso com área vermelha dominante distante;
- caso com XLS complexo;
- caso com desenho simplificado.

## Critério de pronto

A fase está pronta quando os 155 casos rodam automaticamente e o benchmark identifica exatamente se o output final é homologável, precisa de edição ou deve ser bloqueado.
