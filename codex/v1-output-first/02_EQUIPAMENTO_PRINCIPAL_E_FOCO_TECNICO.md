# Fase 2 — Equipamento principal e foco técnico

Objetivo: impedir que o sistema gere croqui final com equipamento principal ou foco técnico diferente do output esperado.

Este é o núcleo do problema de geração errada.

## Regra principal

O equipamento principal do output final deve vir do `CroquiOutputContract` sempre que o contrato tiver `expected_equipment_label`.

Exemplo:

```text
expected_equipment_label = TR 634087
```

Nesse caso, o output final não pode sair como:

```text
TR 1297574
```

Mesmo que `634087` apareça em algum ponto do desenho.

## Tarefa 1 — Centralizar resolução do equipamento principal

Criar módulo:

`croqui_engine/core/primary_equipment.py`

Funções esperadas:

```python
def resolve_primary_equipment(contract, parsed_payload, spatial_candidates) -> PrimaryEquipmentResult:
    ...
```

Resultado esperado:

```python
class PrimaryEquipmentResult:
    label: str
    equipment_type: str
    code: str
    source: str
    confidence: float
    candidates: list[dict]
    warnings: list[str]
```

Prioridade:

1. output contract;
2. target XLSX profile;
3. target PDF profile;
4. filename/registry;
5. plano de execução;
6. cabeçalho do projeto bruto;
7. inferência espacial.

A inferência espacial só pode atuar se as fontes anteriores estiverem vazias ou explicitamente inconclusivas.

## Tarefa 2 — Remover prioridade indevida por proximidade

Auditar regras em:

- `croqui_engine/core/pipeline.py`
- `croqui_engine/topology/equipment_association_v2.py`
- `croqui_engine/parser/spatial.py`
- `croqui_engine/rendering/svg_croqui_renderer.py`

Qualquer regra que promova transformador/chave/religador apenas por proximidade da maior área vermelha deve virar critério auxiliar, nunca fonte dominante quando houver contrato.

## Tarefa 3 — Foco técnico do output

Criar módulo:

`croqui_engine/core/output_focus.py`

Funções:

```python
def resolve_output_focus(contract, primary_equipment, extracted_entities, graph) -> OutputFocusResult:
    ...
```

O foco técnico deve determinar:

- código primário do foco;
- bbox/região de foco;
- elementos mantidos;
- elementos descartados;
- justificativa técnica;
- confiança.

Para o caso TR 634087, o output deve focar no trecho do `634087`, mantendo elementos necessários do croqui oficial e impedindo que `1297574` domine o cabeçalho ou o layout.

## Tarefa 4 — Bloqueio de output final

Se o equipamento principal resolvido divergir do contrato:

```text
expected = TR 634087
generated = TR 1297574
```

O sistema deve:

- bloquear `croqui_final`;
- gerar somente output de revisão, se aplicável;
- registrar `PRIMARY_EQUIPMENT_MISMATCH`;
- impedir score técnico máximo;
- impedir exportação final sem correção manual.

## Tarefa 5 — Testes obrigatórios

Criar testes:

- `tests/test_primary_equipment_contract.py`
- `tests/test_output_focus_selection.py`

Casos mínimos:

1. contrato `TR 634087`, candidatos incluindo `TR 1297574`; resultado deve ser `TR 634087`.
2. contrato `FU 613438`, candidatos incluindo transformadores próximos; resultado deve ser `FU 613438`.
3. sem contrato, usar plano de execução.
4. sem plano de execução, usar cabeçalho.
5. sem cabeçalho, usar inferência espacial com flag de baixa confiança.

## Critério de pronto

A fase está pronta quando o sistema não consegue mais gerar output final com cabeçalho divergente do contrato sem reprovação bloqueante.
