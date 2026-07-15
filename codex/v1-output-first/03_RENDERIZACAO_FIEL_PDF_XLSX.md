# Fase 3 — Renderização fiel PDF/XLSX

Objetivo: tornar PDF e XLSX outputs derivados de um mesmo estado final validado, com fidelidade visual ao padrão Jobel/RGE.

O foco desta fase é output, não arquitetura abstrata.

## Problema a evitar

O sistema não pode gerar:

- PDF com um equipamento;
- XLS/XLSX com outro equipamento;
- desenho baseado em região errada;
- tabela/cabeçalho divergente;
- traçado do projeto bruto usado diretamente como croqui final.

## Tarefa 1 — Estado final de renderização

Criar ou formalizar um objeto de renderização final. Nome sugerido:

`CroquiRenderModel`

Ele não é o produto por si só. Ele existe apenas para garantir que PDF, XLSX e editor renderizem a mesma coisa.

Campos mínimos:

```python
class CroquiRenderModel:
    header: dict
    drawing_elements: list
    connections: list
    labels: list
    work_zones: list
    viability_table: dict
    legend: dict
    page_layout: dict
    output_contract: CroquiOutputContract
    validation_state: dict
```

Regra obrigatória:

`PDF final`, `XLSX final` e `preview/editor` devem usar o mesmo `CroquiRenderModel`.

Se o modelo não consegue gerar PDF/XLSX fiel, corrija o modelo ou o renderer. Não aceite divergência.

## Tarefa 2 — PDF final

Auditar:

- `croqui_engine/generators/pdf_croqui_generator.py`
- `croqui_engine/rendering/svg_croqui_renderer.py`
- `croqui_engine/rendering/final_croqui_renderer.py`
- `croqui_engine/rendering/croqui_renderer_v2.py`
- `croqui_engine/rendering/viability_table_renderer.py`

Regras:

1. cabeçalho vem do contrato/modelo final;
2. equipamento no cabeçalho deve bater com equipamento principal;
3. desenho deve vir do foco técnico validado;
4. `clean_project_trace` pode ser usado como insumo, jamais como output final sem seleção/finalização;
5. símbolos e labels devem ser posicionados pelo modelo final, não por heurística final de última hora;
6. tabela e legenda devem seguir o padrão do croqui ideal.

## Tarefa 3 — XLSX final

Auditar:

- `croqui_engine/generators/excel_generator.py`
- `croqui_engine/excel/template_selector.py`
- `croqui_engine/excel/template_profiler.py`
- `croqui_engine/excel/sheet_profiler.py`
- `croqui_engine/excel/xls_reader.py`

Regras:

1. quando houver XLSX/XLS ideal ou template compatível, usar como base;
2. preservar estilos, merges, larguras, alturas, print area, bordas, orientação e escala;
3. preencher cabeçalho a partir do contrato/modelo final;
4. inserir desenho final no local correto;
5. validar célula/posição do equipamento depois da gravação;
6. se XLSX final contém equipamento diferente do PDF final, bloquear.

## Tarefa 4 — Paridade PDF/XLSX

Criar validador:

`croqui_engine/validation/output_parity.py`

Validar:

- equipamento do PDF = equipamento do XLSX;
- município igual;
- data igual;
- responsável igual;
- códigos principais iguais;
- hash/assinatura do desenho coerente;
- tabela de viabilidade coerente.

## Tarefa 5 — Exportação após edição

O exportador deve aceitar o estado editado pelo editor e gerar output final sem reexecutar inferência de foco.

Regra:

Depois que o usuário editou, o sistema não deve “pensar de novo” e trocar equipamento, foco ou layout.

## Critério de pronto

A fase está pronta quando um mesmo estado final gera PDF e XLSX com cabeçalho, foco e desenho compatíveis, e divergências bloqueiam exportação final.
