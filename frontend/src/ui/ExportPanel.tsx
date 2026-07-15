import type { ExportResponse } from '../types/croquiGraph'

interface Props {
  disabled: boolean
  result: ExportResponse | null
  onExport: () => void
}

export function ExportPanel({ disabled, result, onExport }: Props) {
  return (
    <section className="panel">
      <div className="panel-title">Exportação</div>
      <button className="primary" disabled={disabled} onClick={onExport}>Exportar PDF/XLS</button>
      {result && (
        <div className="artifact-list">
          {result.artifacts
            .filter((item) => ['pdf', 'xls', 'svg', 'report'].includes(item.kind))
            .map((item) => (
              <a key={item.kind} href={item.download_url} target="_blank" rel="noreferrer">{item.label}</a>
            ))}
        </div>
      )}
    </section>
  )
}
