# CroquiMaker Diagram Engine

## Novo fluxo

O Python não é mais a fonte principal de desenho/layout do croqui final no fluxo novo.

Fluxo:

`PDF bruto -> Python extraction -> CroquiGraph JSON -> TypeScript DiagramEngine -> SVG final editado -> Python exporter -> PDF/XLS`

O backend continua responsável por:

- extrair texto/vetores do PDF bruto;
- identificar entidades técnicas;
- resolver equipamento principal;
- montar e validar o grafo técnico;
- exportar PDF/XLS a partir do SVG final recebido.

O frontend passa a ser responsável por:

- renderizar o `CroquiGraph`;
- aplicar layout automático;
- permitir edição visual;
- exportar o SVG final.

## yFiles

A fronteira de integração é:

`frontend/src/diagram/DiagramEngineAdapter.ts`

Implementação preparada:

`frontend/src/diagram/yfiles/YFilesDiagramEngine.ts`

Como yFiles é proprietário, ele não é versionado neste repositório. Para ativar:

1. Instale o pacote/licença yFiles conforme o contrato do fornecedor.
2. Substitua o corpo de `YFilesDiagramEngine` para criar `GraphComponent`.
3. Mapeie `CroquiGraph.nodes/edges/labels/workZones` para o graph yFiles.
4. Aplique `OrthogonalLayout`, `HierarchicLayout` e `OrthogonalEdgeRouter`.
5. Faça `exportSvg()` retornar o SVG do graph yFiles.

Enquanto yFiles não estiver instalado, o editor usa fallback SVG com ELK.js quando disponível.

## APIs

- `POST /api/projects/upload`
- `POST /api/projects/{id}/extract-graph`
- `GET /api/projects/{id}/graph`
- `POST /api/projects/{id}/export`

O endpoint de export recebe:

```json
{
  "graph": {},
  "svg": "<svg>...</svg>"
}
```

O Python não reinterpreta nem redesenha o croqui nessa etapa. PDF e XLS são gerados a partir do mesmo SVG recebido.
