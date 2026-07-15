# AGENTS.md — tests

## Missão

Proteger a V1 contra regressões de output.

## Prioridades de teste

1. Equipamento principal correto.
2. Foco técnico correto.
3. Paridade PDF/XLSX.
4. Bloqueio de output divergente.
5. Editor preservando alterações na exportação.
6. Corpus de 155 casos rodando como benchmark.

## Testes negativos obrigatórios

- esperado `TR 634087`, gerado `TR 1297574` deve bloquear;
- esperado `FU 613438`, transformador próximo não pode virar principal;
- código esperado presente como secundário não pode aprovar output;
- PDF correto e XLSX divergente deve bloquear;
- exportação após edição não pode reexecutar inferência.

## Golden cases

Manter conjunto pequeno de casos representativos para CI rápido, e corpus completo para benchmark/homologação.

## Critério

Nenhum teste deve aprovar apenas por presença parcial de código. Testes devem validar output final.
