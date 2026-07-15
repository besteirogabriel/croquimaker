# Fase 7 — Migração incremental sem reescrita total

Objetivo: implementar a V1 sem jogar fora o que já funciona.

O problema não exige trocar Python nem reescrever todo o sistema. Exige mudar o eixo de decisão para output final, corrigir seleção de foco, garantir paridade PDF/XLSX e criar editor com exportação fiel.

## Estratégia

Manter:

- Python como engine;
- módulos de extração existentes;
- parser e grafo existentes como insumos;
- geração atual como base inicial;
- Flask se necessário no curto prazo;
- corpus/benchmark atual como base.

Refatorar:

- contrato de output;
- equipamento principal;
- foco técnico;
- renderer final;
- gerador XLSX;
- validação bloqueante;
- interface de revisão para editor real.

Adicionar:

- `CroquiOutputContract`;
- `CroquiRenderModel` ou modelo equivalente de renderização final;
- validador de paridade PDF/XLSX;
- editor online com SVG;
- benchmark output-first.

## Fases incrementais

### Etapa A — Sem editor ainda

1. Criar contrato de output.
2. Corrigir equipamento principal.
3. Corrigir foco técnico.
4. Bloquear output divergente.
5. Rodar golden cases.

### Etapa B — Renderização e XLSX

1. Unificar modelo de render PDF/XLSX.
2. Usar template XLSX quando disponível.
3. Validar paridade.
4. Rodar 155 casos.

### Etapa C — Editor

1. Criar endpoints de modelo final.
2. Criar editor SVG.
3. Salvar alterações.
4. Exportar sem reinferência.
5. Validar output editado.

### Etapa D — Homologação V1

1. Rodar benchmark completo.
2. Gerar relatório executivo.
3. Definir limiares.
4. Bloquear regressões.

## Não fazer

- Não pausar tudo para migrar Flask para FastAPI.
- Não substituir engine por Node/Go/Java.
- Não construir editor antes de estabilizar contrato de output.
- Não criar modelo intermediário que não gere PDF/XLSX fiel.
- Não aceitar exportação final sem relatório de validação.

## Critério de pronto

A migração está correta quando cada etapa gera valor funcional medível no output, mesmo antes do editor completo estar pronto.
