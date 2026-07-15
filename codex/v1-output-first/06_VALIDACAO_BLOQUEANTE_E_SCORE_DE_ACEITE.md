# Fase 6 — Validação bloqueante e score de aceite

Objetivo: substituir métricas fracas por validação orientada a output final.

A métrica não pode aprovar um croqui só porque encontrou um código esperado em algum lugar. O output precisa estar correto como documento final.

## Tarefa 1 — Auditar métricas atuais

Inspecionar:

- `croqui_engine/benchmark/technical_metrics.py`
- `croqui_engine/benchmark/visual_metrics.py`
- `croqui_engine/benchmark/text_metrics.py`
- `croqui_engine/benchmark/metrics.py`
- `croqui_engine/benchmark/runner.py`

Identificar onde o sistema atribui score alto por presença parcial de código ou texto.

## Tarefa 2 — Criar validador de aceite

Criar módulo:

`croqui_engine/validation/output_acceptance.py`

Função:

```python
def validate_output_acceptance(contract, pdf_output, xlsx_output, render_model) -> OutputAcceptanceResult:
    ...
```

Resultado:

```python
class OutputAcceptanceResult:
    status: Literal["PASSED", "BLOCKED", "DRAFT_REVIEW_REQUIRED"]
    final_output_allowed: bool
    blocking_errors: list[str]
    warnings: list[str]
    scores: dict
```

## Tarefa 3 — Erros bloqueantes

Implementar pelo menos:

- `PRIMARY_EQUIPMENT_MISMATCH`
- `PDF_HEADER_EQUIPMENT_MISMATCH`
- `XLSX_HEADER_EQUIPMENT_MISMATCH`
- `PDF_XLSX_HEADER_MISMATCH`
- `PRIMARY_FOCUS_MISMATCH`
- `UNVALIDATED_CLEAN_TRACE_AS_FINAL`
- `MISSING_REQUIRED_HEADER_FIELD`
- `MISSING_REQUIRED_OUTPUT_CODES`
- `FORBIDDEN_CODE_AS_PRIMARY_FOCUS`
- `EXPORT_FROM_STALE_MODEL`

## Tarefa 4 — Score de qualidade

Separar bloqueio de score.

Um output pode ter score visual 85%, mas se equipamento principal diverge, deve ser bloqueado.

Scores sugeridos:

```json
{
  "critical_pass": true,
  "header_score": 1.0,
  "primary_equipment_score": 1.0,
  "focus_score": 0.95,
  "required_codes_score": 0.87,
  "visual_similarity_score": 0.78,
  "xlsx_fidelity_score": 0.92,
  "overall_output_score": 0.88
}
```

## Tarefa 5 — Estados de saída

Definir estados claros:

- `FINAL_VALIDATED`: pode ser entregue;
- `DRAFT_NEEDS_REVIEW`: pode ser editado, não é final;
- `BLOCKED_CRITICAL`: não exportar como final;
- `EXPORTED_AFTER_MANUAL_REVIEW`: exportado após edição humana e validação.

## Tarefa 6 — Teste negativo explícito

Criar teste:

Input:

```json
{
  "expected_equipment_label": "TR 634087",
  "generated_pdf_header": "TR 1297574",
  "detected_codes": ["634087", "1297574"]
}
```

Resultado obrigatório:

```json
{
  "status": "BLOCKED",
  "final_output_allowed": false,
  "blocking_errors": ["PRIMARY_EQUIPMENT_MISMATCH"]
}
```

## Critério de pronto

A fase está pronta quando nenhum output criticamente divergente consegue ser rotulado como final, mesmo que contenha textos/códigos esperados em regiões secundárias.
