import type { CroquiGraph } from '../types/croquiGraph'

export function ValidationPanel({ graph }: { graph: CroquiGraph | null }) {
  if (!graph) {
    return (
      <section className="panel">
        <div className="panel-title">Validação</div>
        <div className="muted">Nenhum graph carregado.</div>
      </section>
    )
  }
  const messages = [...graph.validation.blockingErrors, ...graph.validation.warnings]
  return (
    <section className="panel">
      <div className="panel-title">Validação</div>
      <div className={`status-pill ${graph.validation.status}`}>{graph.validation.status}</div>
      <dl className="metrics">
        <dt>Nós</dt><dd>{graph.nodes.length}</dd>
        <dt>Arestas</dt><dd>{graph.edges.length}</dd>
        <dt>Principal</dt><dd>{graph.mainEquipment.type} {graph.mainEquipment.code}</dd>
      </dl>
      {messages.length === 0 ? (
        <div className="status-ok">Sem avisos.</div>
      ) : (
        <ul className="message-list">
          {messages.map((item, index) => (
            <li key={index}>{String(item.code ?? item.message ?? 'warning')}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
