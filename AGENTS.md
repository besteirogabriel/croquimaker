# AGENTS.md — CroquiMaker V1 Output-First

## Missão

Implementar a V1 do CroquiMaker com foco absoluto no output final: PDF e XLSX corretos, editáveis e homologáveis.

O sistema pode usar modelos intermediários, cenas, grafos e payloads, mas nenhum deles é objetivo final. O sucesso é medido pelo output.

## Prioridade de produto

1. Output final correto.
2. Paridade PDF/XLSX.
3. Equipamento principal e foco técnico corretos.
4. Editor que altera exatamente o que será exportado.
5. Corpus de 155 casos como homologação.
6. Código limpo, testável e incremental.

## Regras obrigatórias

- Não aceitar output final com equipamento principal divergente.
- Não considerar presença secundária de código como acerto crítico.
- Não usar `clean_project_trace` como final validado sem seleção/foco/validação.
- Não fazer o editor editar uma representação diferente da exportação.
- Não reexecutar inferência automática sobre um croqui editado manualmente antes da exportação final.
- Não remover metadados de corpus/contrato antes da validação.

## Linguagem e estilo

- Código em Python para engine atual.
- TypeScript/React/SVG para editor, quando implementado.
- Funções pequenas e testáveis.
- Relatórios JSON claros.
- Testes para regressões reais.

## Antes de alterar

1. Identifique qual output será afetado: PDF, XLSX, editor ou validação.
2. Verifique se há contrato de output aplicável.
3. Preserve compatibilidade com o fluxo existente quando possível.
4. Adicione ou atualize testes.

## Critério de merge

Nenhum patch deve ser aceito se:

- melhora modelo interno mas piora PDF/XLSX;
- aumenta score fraco sem melhorar output;
- permite cabeçalho divergente;
- quebra paridade entre editor e exportador;
- não adiciona teste para caso crítico.
