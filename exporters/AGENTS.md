# AGENTS.md — generators/exporters

## Missão

Garantir que PDF e XLSX sejam outputs fiéis do mesmo estado final validado.

## Regras para PDF

- Cabeçalho vem do contrato/modelo final.
- Desenho vem do foco técnico validado.
- Tabela e legenda seguem padrão oficial.
- Não usar trace bruto como final sem validação.

## Regras para XLSX

- Usar template oficial/compatível quando disponível.
- Preservar estilos, merges, print area, larguras, alturas, bordas e escala.
- Preencher campos críticos a partir do mesmo modelo do PDF.
- Validar o arquivo salvo reabrindo e lendo campos críticos.

## Paridade

Sempre validar:

- PDF equipment == XLSX equipment;
- PDF município == XLSX município;
- PDF data == XLSX data;
- PDF responsável == XLSX responsável;
- códigos principais coerentes.

## Não fazer

- PDF e XLSX com pipelines independentes que possam divergir.
- XLSX do zero quando existe template de referência aplicável.
- Exportar final se o modelo está com status bloqueado.
