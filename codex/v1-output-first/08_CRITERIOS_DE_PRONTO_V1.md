# Critérios de pronto — CroquiMaker V1

A V1 só deve ser considerada pronta quando o sistema entregar output final confiável, editável e homologável.

## Critérios bloqueantes

### 1. Output correto manda

- PDF e XLSX finais são os artefatos de aceite.
- Modelo interno só conta se reproduzir o output final corretamente.
- Editor só conta se exportar exatamente o que foi editado.

### 2. Equipamento principal

- O equipamento do cabeçalho deve bater com o equipamento principal esperado.
- O equipamento principal deve bater entre PDF, XLSX e relatório de validação.
- Código esperado como elemento secundário não valida o output.

### 3. Foco técnico

- O foco visual/técnico deve corresponder ao equipamento principal.
- Elementos remotos não podem dominar o output final.
- Área vermelha, labels e conexões devem ser coerentes com o foco.

### 4. PDF/XLSX

- PDF final e XLSX final devem ter cabeçalhos consistentes.
- XLSX deve preservar padrão, estilos, estrutura e impressão do template quando disponível.
- PDF deve refletir o mesmo desenho validado.

### 5. Editor

- Usuário consegue corrigir equipamento principal.
- Usuário consegue mover/adicionar/remover elementos essenciais.
- Usuário consegue corrigir labels, conexões, área vermelha e tabela/cabeçalho.
- Exportação depois da edição não reexecuta inferência que desfaça a correção.

### 6. Corpus

- 155 casos rodam no benchmark output-first.
- Cada caso recebe status claro: aprovado, precisa revisão ou bloqueado.
- Relatório mostra motivo técnico de cada bloqueio.
- Golden cases rodam em CI/regressão.

## Métricas mínimas sugeridas

- 100% de bloqueio para divergência de equipamento principal.
- 100% de paridade de cabeçalho entre PDF e XLSX em outputs finais.
- 0 outputs finais com `PRIMARY_EQUIPMENT_MISMATCH`.
- 0 outputs finais com `PDF_XLSX_HEADER_MISMATCH`.
- Relatório JSON produzido em 100% das gerações.
- Editor preserva 100% das alterações manuais na exportação.

## Definição de V1 pronta

A V1 está pronta quando:

1. gera rascunhos automáticos de qualidade prática;
2. permite edição manual total dos itens que impactam o output;
3. exporta PDF/XLSX fiéis ao estado final;
4. impede entrega final com divergência crítica;
5. mede tudo contra os 155 casos reais;
6. mantém regressão automatizada para os casos críticos.
