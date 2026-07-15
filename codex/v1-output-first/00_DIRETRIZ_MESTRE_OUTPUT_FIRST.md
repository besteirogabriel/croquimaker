# Prompt mestre — CroquiMaker V1 Output-First

Você está trabalhando no repositório CroquiMaker.

A prioridade da V1 é resolver a geração incorreta dos croquis pelo ponto que importa para o usuário: **o output final**.

Não trate `CroquiScene`, JSON interno, grafo ou payload como produto final. Eles podem existir apenas como meios técnicos. A entrega que importa é:

1. PDF final fiel ao croqui ideal;
2. XLSX final fiel ao croqui ideal;
3. editor online capaz de corrigir visualmente o croqui e exportar o mesmo resultado corrigido;
4. validação automática que impeça outputs finais com equipamento/foco/layout divergentes.

## Regra de arquitetura

A V1 deve seguir o princípio:

`output correto primeiro; modelo intermediário depois`.

Qualquer estrutura interna precisa provar que consegue gerar PDF/XLSX corretos. Se uma abstração melhora o código mas não melhora a fidelidade do output, ela não é prioridade da V1.

## Problema funcional a resolver

O sistema atual pode gerar um croqui visualmente plausível, mas com foco técnico diferente do croqui ideal. Exemplo observado:

- croqui oficial esperado: `TR 634087`;
- output gerado: `TR 1297574`;
- o código `634087` aparece no desenho, mas não como equipamento principal nem como foco do output.

Esse comportamento não deve ser aceito na V1. A validação não pode considerar correto apenas porque um código esperado aparece em algum ponto do desenho.

## Resultado esperado da V1

A V1 deve ser capaz de:

- gerar croqui inicial de qualquer projeto com meta mínima de confiabilidade prática;
- identificar equipamento principal, foco técnico, elementos mantidos e elementos descartados;
- produzir output PDF/XLSX dentro do padrão visual e funcional dos croquis ideais;
- permitir edição online de todos os componentes que impactam o output;
- exportar PDF/XLSX a partir do estado editado;
- usar 155 casos reais como suite de homologação e regressão;
- bloquear outputs finais quando a validação detectar divergência crítica.

## Princípios obrigatórios

1. PDF/XLSX final são os outputs soberanos.
2. O editor deve operar com paridade visual: o que o usuário edita deve ser o que sai no PDF/XLSX.
3. O XLSX ideal deve ser tratado como referência de layout e estrutura, não como arquivo secundário.
4. O PDF ideal deve ser tratado como referência visual e técnica do output final.
5. O corpus de 155 casos deve medir fidelidade de output, não apenas qualidade interna do algoritmo.
6. Heurísticas de extração não podem sobrescrever metadados oficiais, target profile ou equipamento explicitamente definido.
7. `clean_project_trace` ou qualquer cópia simplificada do projeto bruto não pode virar final sem passar por seleção de foco, renderização final e validação de output.

## Caminhos principais a auditar

- `croqui_engine/core/pipeline.py`
- `croqui_engine/parser/project_text_parser.py`
- `croqui_engine/parser/equipment_parser.py`
- `croqui_engine/extraction/vector_trace.py`
- `croqui_engine/topology/graph_builder.py`
- `croqui_engine/topology/graph_builder_v2.py`
- `croqui_engine/topology/equipment_association_v2.py`
- `croqui_engine/rendering/svg_croqui_renderer.py`
- `croqui_engine/rendering/final_croqui_renderer.py`
- `croqui_engine/rendering/croqui_renderer_v2.py`
- `croqui_engine/generators/pdf_croqui_generator.py`
- `croqui_engine/generators/excel_generator.py`
- `croqui_engine/excel/template_selector.py`
- `croqui_engine/excel/template_profiler.py`
- `croqui_engine/corpus/reference_outputs.py`
- `croqui_engine/corpus/registry.py`
- `croqui_engine/benchmark/technical_metrics.py`
- `croqui_engine/benchmark/visual_metrics.py`
- `croqui_engine/benchmark/runner.py`

## Não fazer

- Não transformar a V1 em um projeto acadêmico de modelagem abstrata.
- Não tratar JSON intermediário como sucesso se PDF/XLSX final estiverem errados.
- Não criar um editor que edita uma representação diferente da exportação final.
- Não aceitar métrica fraca baseada somente em presença de códigos.
- Não gerar `croqui_final` quando a validação de output reprovar.

## Entregáveis

1. Contrato de output final.
2. Correção da escolha de equipamento principal/foco técnico.
3. Renderização fiel PDF/XLSX orientada por template e referência.
4. Editor online com paridade de output.
5. Validação bloqueante por output.
6. Corpus de 155 casos como regressão/homologação.
7. Relatório por geração mostrando por que o output foi aceito ou bloqueado.
