# Fase 1 — Mapear engine atual e definir contrato de output

Objetivo: documentar e implementar um contrato técnico claro para o output final da V1.

A V1 não deve ser guiada por “cena editável” como fim em si. Ela deve ser guiada por um contrato de output que define o que significa um croqui final correto.

## Tarefa 1 — Mapear fluxo atual

Inspecione o fluxo completo desde upload até geração final:

- entrada do projeto PDF;
- extração textual e vetorial;
- parser de equipamentos;
- montagem de payload;
- inferência de equipamento principal;
- montagem de grafo/topologia;
- renderização PDF;
- geração XLS/XLSX;
- benchmark e métricas.

Produza um documento em `docs/v1/output_pipeline_map.md` com:

- módulos chamados em ordem;
- dados que entram e saem de cada etapa;
- onde o equipamento principal é definido;
- onde o cabeçalho é preenchido;
- onde o desenho final é montado;
- onde o XLS/PDF divergem ou podem divergir;
- onde o corpus ou reference outputs entram no fluxo.

## Tarefa 2 — Criar contrato de output

Criar módulo:

`croqui_engine/core/output_contract.py`

O contrato deve definir, no mínimo:

```python
class CroquiOutputContract:
    expected_equipment_type: str | None
    expected_equipment_code: str | None
    expected_equipment_label: str | None
    expected_header: dict
    expected_visible_codes: list[str]
    expected_primary_focus_code: str | None
    expected_required_codes: list[str]
    expected_forbidden_primary_codes: list[str]
    reference_pdf_path: str | None
    reference_xlsx_path: str | None
    reference_case_id: str | None
    source_priority: list[str]
```

O contrato deve ser carregado por prioridade:

1. XLSX ideal do corpus, quando existir;
2. PDF ideal do corpus, quando existir;
3. nome do arquivo ideal;
4. registry/ground truth;
5. plano de execução do projeto;
6. cabeçalho textual do projeto;
7. inferência espacial.

## Tarefa 3 — Garantir que o output contract esteja disponível no pipeline

Modificar o pipeline para que o contrato seja criado antes de:

- escolher equipamento principal;
- escolher foco visual;
- construir render final;
- gerar XLSX;
- gerar PDF;
- calcular métrica técnica.

Nenhuma etapa posterior pode sobrescrever um campo vindo de fonte mais confiável.

## Tarefa 4 — Relatório de output

Criar JSON lateral por geração:

`output_validation_report.json`

Campos mínimos:

```json
{
  "contract": {
    "expected_equipment_label": "TR 634087",
    "expected_equipment_source": "target_xlsx"
  },
  "generated": {
    "pdf_header_equipment": "TR 634087",
    "xlsx_header_equipment": "TR 634087",
    "primary_focus_code": "634087",
    "visible_codes": []
  },
  "validation": {
    "status": "PASSED" | "BLOCKED" | "DRAFT_REVIEW_REQUIRED",
    "blocking_errors": [],
    "warnings": []
  }
}
```

## Critério de pronto

A fase está pronta quando:

- existe contrato de output versionado;
- o pipeline carrega o contrato antes da inferência;
- PDF e XLSX recebem os mesmos metadados do contrato;
- há relatório JSON por geração;
- testes cobrem pelo menos o caso TR 634087 e um caso FU 613438.
