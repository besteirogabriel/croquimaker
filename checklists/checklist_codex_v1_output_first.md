# Checklist operacional para o Codex — V1 Output-First

## Antes de começar

- [ ] Li `00_DIRETRIZ_MESTRE_OUTPUT_FIRST.md`.
- [ ] Entendi que o objetivo é PDF/XLSX final, não modelo intermediário.
- [ ] Identifiquei quais módulos do output serão afetados.

## Contrato

- [ ] Existe `CroquiOutputContract`.
- [ ] Contrato vem antes da inferência.
- [ ] Contrato preserva fonte dos dados.
- [ ] Heurística não sobrescreve contrato.

## Equipamento e foco

- [ ] Equipamento principal vem do contrato quando disponível.
- [ ] Presença secundária de código não aprova output.
- [ ] Foco técnico é calculado e registrado.
- [ ] Divergência crítica bloqueia final.

## PDF/XLSX

- [ ] PDF e XLSX usam o mesmo estado final.
- [ ] Cabeçalhos são consistentes.
- [ ] XLSX usa template quando disponível.
- [ ] Exportador reabre e valida o XLSX salvo.
- [ ] Relatório JSON é gerado.

## Editor

- [ ] Editor edita o modelo de output real.
- [ ] Exportação não desfaz edição manual.
- [ ] Preview e PDF/XLSX têm paridade.

## Corpus

- [ ] 155 casos importáveis.
- [ ] Golden cases definidos.
- [ ] Benchmark output-first disponível.
- [ ] Relatório executivo gerado.

## Aceite

- [ ] Nenhum output final com equipamento divergente passa.
- [ ] Nenhum PDF/XLSX divergente passa.
- [ ] Testes negativos cobrem TR 634087 e FU 613438.
