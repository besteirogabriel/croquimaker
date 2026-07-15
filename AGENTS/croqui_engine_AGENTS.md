# AGENTS.md — croqui_engine

## Escopo

Este diretório contém o engine de extração, inferência, renderização, geração e validação. A prioridade é output final correto.

## Áreas críticas

- `core/pipeline.py`
- `core/output_contract.py`
- `core/primary_equipment.py`
- `core/output_focus.py`
- `parser/`
- `extraction/`
- `topology/`
- `rendering/`
- `generators/`
- `excel/`
- `benchmark/`
- `corpus/`
- `validation/`

## Regras

1. O contrato de output deve ser carregado antes da inferência de equipamento/foco.
2. Equipamento principal vindo do contrato não pode ser sobrescrito por heurística espacial.
3. A renderização final deve usar foco técnico validado.
4. PDF e XLSX devem usar o mesmo estado final.
5. Qualquer output final precisa passar por validação bloqueante.

## Proibido

- Métrica crítica baseada apenas em `expected_code in detected_codes`.
- Promover equipamento por proximidade quando contrato existe.
- Gerar `croqui_final` com status bloqueado.
- Corrigir apenas CSS/layout ignorando divergência técnica.

## Testes esperados

- equipamento principal por contrato;
- foco técnico por contrato;
- bloqueio de divergência;
- paridade PDF/XLSX;
- XLSX com template;
- regressão de golden cases.
