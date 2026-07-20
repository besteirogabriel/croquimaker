import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { createDiagramEngine } from '../diagram/createDiagramEngine'
import type { DiagramEngineAdapter } from '../diagram/DiagramEngineAdapter'
import type { CroquiEdge, CroquiGraph, CroquiNode } from '../types/croquiGraph'

export interface DiagramCanvasHandle {
  applyAutoLayout: () => Promise<void>
  exportSvg: () => Promise<string>
  undo: () => void
  redo: () => void
  getGraph: () => CroquiGraph | null
  updateHeader: (header: CroquiGraph['header']) => void
  updateElement: (id: string, patch: Partial<unknown>) => void
  deleteElement: (id: string) => void
  addNode: (node: CroquiNode) => void
  addEdge: (edge: CroquiEdge) => void
}

interface Props {
  graph: CroquiGraph | null
  selectedId: string
  onGraphChange: (graph: CroquiGraph) => void
  onSelect: (id: string) => void
}

export const DiagramCanvas = forwardRef<DiagramCanvasHandle, Props>(function DiagramCanvas(
  { graph, selectedId, onGraphChange, onSelect },
  ref
) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const engineRef = useRef<DiagramEngineAdapter | null>(null)

  useEffect(() => {
    if (!hostRef.current || engineRef.current) return
    engineRef.current = createDiagramEngine(hostRef.current, { onGraphChange, onSelect })
  }, [onGraphChange, onSelect])

  useEffect(() => {
    if (!engineRef.current || !graph) return
    engineRef.current.loadGraph(graph)
  }, [graph?.id])

  useEffect(() => {
    if (!engineRef.current || !selectedId) return
    engineRef.current.selectElement(selectedId)
  }, [selectedId])

  useImperativeHandle(ref, () => ({
    applyAutoLayout: () => engineRef.current?.applyAutoLayout() ?? Promise.resolve(),
    exportSvg: () => engineRef.current?.exportSvg() ?? Promise.resolve(''),
    undo: () => engineRef.current?.undo(),
    redo: () => engineRef.current?.redo(),
    getGraph: () => engineRef.current?.getGraph() ?? null,
    updateHeader: (header) => engineRef.current?.updateHeader(header),
    updateElement: (id, patch) => engineRef.current?.updateElement(id, patch),
    deleteElement: (id) => engineRef.current?.deleteElement(id),
    addNode: (node) => engineRef.current?.addNode(node),
    addEdge: (edge) => engineRef.current?.addEdge(edge)
  }))

  return (
    <div className="canvas-wrap">
      <div ref={hostRef} className="diagram-host" />
      {!graph && <div className="empty-canvas">Envie um PDF para gerar o CroquiGraph.</div>}
    </div>
  )
})
