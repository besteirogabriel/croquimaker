import type { CroquiGraph, CroquiNode } from '../types/croquiGraph'

interface Props {
  graph: CroquiGraph
  selectedId: string
  onHeaderChange: (key: keyof CroquiGraph['header'], value: string) => void
  onSelectedPatch: (patch: Partial<Record<string, unknown>>) => void
  onAddNode: (kind: CroquiNode['kind']) => void
  onAddEdge: (source: string, target: string) => void
  onDeleteSelected: () => void
}

export function PropertiesPanel({
  graph,
  selectedId,
  onHeaderChange,
  onSelectedPatch,
  onAddNode,
  onAddEdge,
  onDeleteSelected
}: Props) {
  const selectedNode = graph.nodes.find((node) => node.id === selectedId)
  const selectedEdge = graph.edges.find((edge) => edge.id === selectedId)
  const selectedLabel = graph.labels.find((label) => label.id === selectedId)
  const selectedZone = graph.workZones.find((zone) => zone.id === selectedId)

  return (
    <section className="panel properties">
      <div className="panel-title">Propriedades</div>
      <label>Departamento<input value={graph.header.departamento} onChange={(event) => onHeaderChange('departamento', event.target.value)} /></label>
      <label>Município<input value={graph.header.municipio} onChange={(event) => onHeaderChange('municipio', event.target.value)} /></label>
      <label>Equipamento<input value={graph.header.equipamento} onChange={(event) => onHeaderChange('equipamento', event.target.value)} /></label>
      <label>Data<input value={graph.header.data_levantamento} onChange={(event) => onHeaderChange('data_levantamento', event.target.value)} /></label>
      <label>Responsável<input value={graph.header.responsavel} onChange={(event) => onHeaderChange('responsavel', event.target.value)} /></label>

      <div className="split-line" />
      <div className="panel-subtitle">Selecionado</div>
      {!selectedId && <div className="muted">Selecione um nó ou área no desenho.</div>}
      {selectedNode && (
        <div className="property-grid">
          <label>ID<input value={selectedNode.id} readOnly /></label>
          <label>Código<input value={selectedNode.code} onChange={(event) => onSelectedPatch({ code: event.target.value })} /></label>
          <label>Tipo<input value={selectedNode.equipmentType} onChange={(event) => onSelectedPatch({ equipmentType: event.target.value })} /></label>
          <label>
            Principal
            <input type="checkbox" checked={selectedNode.isMain} onChange={(event) => onSelectedPatch({ isMain: event.target.checked })} />
          </label>
        </div>
      )}
      {selectedZone && (
        <div className="property-grid">
          <label>Largura<input type="number" value={selectedZone.width ?? 130} onChange={(event) => onSelectedPatch({ width: Number(event.target.value) })} /></label>
          <label>Altura<input type="number" value={selectedZone.height ?? 76} onChange={(event) => onSelectedPatch({ height: Number(event.target.value) })} /></label>
        </div>
      )}
      {selectedEdge && (
        <div className="property-grid">
          <label>
            Rede
            <select value={selectedEdge.networkType} onChange={(event) => onSelectedPatch({ networkType: event.target.value })}>
              <option value="AT">Primária (AT)</option>
              <option value="BT">Secundária (BT)</option>
              <option value="AT_BT">Primária + secundária</option>
              <option value="UNKNOWN">A confirmar</option>
            </select>
          </label>
          <label>
            Traço
            <select value={selectedEdge.style} onChange={(event) => onSelectedPatch({ style: event.target.value })}>
              <option value="solid">Contínuo</option>
              <option value="dashed">Projetado/tracejado</option>
            </select>
          </label>
        </div>
      )}
      {selectedLabel && (
        <div className="property-grid">
          <label>Texto<input value={selectedLabel.text} onChange={(event) => onSelectedPatch({ text: event.target.value })} /></label>
        </div>
      )}
      {selectedId && <button className="danger" onClick={onDeleteSelected}>Remover selecionado</button>}

      <div className="split-line" />
      <div className="button-row">
        <button onClick={() => onAddNode('pole')}>+ Poste</button>
        <button onClick={() => onAddNode('switch')}>+ Chave</button>
        <button onClick={() => onAddNode('transformer')}>+ TR</button>
      </div>
      <EdgeCreator graph={graph} onAddEdge={onAddEdge} />
    </section>
  )
}

function EdgeCreator({ graph, onAddEdge }: { graph: CroquiGraph; onAddEdge: (source: string, target: string) => void }) {
  const source = graph.nodes[0]?.id ?? ''
  const target = graph.nodes[1]?.id ?? ''
  return (
    <form
      className="edge-form"
      onSubmit={(event) => {
        event.preventDefault()
        const form = new FormData(event.currentTarget)
        onAddEdge(String(form.get('source') ?? ''), String(form.get('target') ?? ''))
      }}
    >
      <select name="source" defaultValue={source}>
        {graph.nodes.map((node) => <option key={node.id} value={node.id}>{node.id}</option>)}
      </select>
      <select name="target" defaultValue={target}>
        {graph.nodes.map((node) => <option key={node.id} value={node.id}>{node.id}</option>)}
      </select>
      <button type="submit">Conectar</button>
    </form>
  )
}
