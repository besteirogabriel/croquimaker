# Fase 4 — Editor online com paridade de output

Objetivo: criar editor online para corrigir o output e garantir que o que o usuário vê/editou seja exatamente o que será exportado.

O editor não é o objetivo isolado. Ele existe para garantir output final correto quando a geração automática não atingir 100%.

## Regra do editor

O editor deve editar o mesmo modelo usado para exportar PDF/XLSX.

Não criar um editor decorativo, mockado ou separado do renderer final.

## Tarefa 1 — API de estado final

Criar endpoints para carregar, salvar, validar e exportar o estado final do croqui:

```text
GET  /api/jobs/{job_id}/output-model
PUT  /api/jobs/{job_id}/output-model
POST /api/jobs/{job_id}/output-model/validate
POST /api/jobs/{job_id}/export/pdf
POST /api/jobs/{job_id}/export/xlsx
```

Se o projeto ainda usa Flask, implemente em Flask. Se a migração para FastAPI for aprovada, mantenha compatibilidade com o app atual.

## Tarefa 2 — Editor visual

Criar frontend em `frontend/` ou integrar ao app existente, usando:

- React;
- TypeScript;
- SVG interativo;
- estado tipado;
- undo/redo;
- painel de propriedades;
- validação em tempo real.

Operações obrigatórias:

### Cabeçalho

- editar departamento;
- editar município;
- editar equipamento;
- editar data;
- editar responsável.

### Equipamentos e símbolos

- trocar equipamento principal;
- alterar tipo e código;
- mover;
- rotacionar;
- adicionar;
- remover;
- marcar como principal.

### Rede

- adicionar nó/poste;
- mover nó/poste;
- remover nó/poste;
- conectar nós;
- remover conexão;
- alterar AT/BT/AT-BT;
- alterar estilo de linha;
- organizar trecho.

### Labels e anotações

- editar texto;
- mover label;
- associar label a elemento;
- adicionar/remover setas;
- adicionar/remover retângulo vermelho tracejado;
- redimensionar área de trabalho.

### Output

- preview PDF;
- exportar PDF;
- exportar XLSX;
- validar antes de exportar final.

## Tarefa 3 — Paridade visual

O editor deve renderizar o mesmo modelo que o exportador usa.

Implementar teste de paridade:

1. carregar modelo;
2. renderizar no editor/SVG;
3. exportar PDF;
4. comparar elementos principais;
5. garantir que mudanças feitas no editor aparecem no output.

## Tarefa 4 — Correção manual de foco

Se o sistema escolher equipamento/foco com confiança abaixo do limiar ou se o usuário quiser corrigir:

- permitir selecionar outro equipamento como principal;
- atualizar cabeçalho;
- recalcular elementos relevantes se solicitado;
- manter edição manual se o usuário não quiser recalcular;
- validar output após alteração.

## Tarefa 5 — Não reexecutar inferência ao exportar edição manual

Ao exportar uma versão editada:

- não trocar equipamento principal automaticamente;
- não redesenhar a topologia do zero;
- não reaplicar cluster vermelho dominante;
- não substituir labels editados;
- não apagar ajustes manuais.

## Critério de pronto

A fase está pronta quando o usuário consegue corrigir visualmente um caso em que o rascunho automático errou o foco, exportar PDF/XLSX, e os arquivos finais refletem exatamente a correção.
