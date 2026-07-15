# AGENTS.md — frontend/editor

## Missão

Criar editor online que corrige o output final. O editor deve ter paridade com a exportação PDF/XLSX.

## Stack recomendada

- React
- TypeScript
- SVG interativo
- Estado tipado
- Undo/redo
- API JSON

## Regra central

O que o usuário vê e edita deve ser o que será exportado. Não criar editor meramente ilustrativo.

## Operações obrigatórias

- editar cabeçalho;
- trocar equipamento principal;
- mover/adicionar/remover equipamentos;
- mover/adicionar/remover postes/nós;
- conectar e desconectar trechos;
- editar labels;
- mover/redimensionar área vermelha;
- editar tabela/campos essenciais;
- validar antes de exportar;
- exportar PDF/XLSX.

## Exportação

Ao exportar croqui editado:

- não reexecutar inferência automática;
- não trocar foco;
- não substituir alterações manuais;
- enviar o estado final editado ao backend;
- mostrar erros bloqueantes se houver.

## Testes

- alteração visual aparece no PDF exportado;
- alteração visual aparece no XLSX exportado quando aplicável;
- troca de equipamento principal atualiza cabeçalho;
- undo/redo preserva estado;
- validação bloqueia final divergente.
