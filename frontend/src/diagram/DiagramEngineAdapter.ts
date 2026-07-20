import type { CroquiEdge, CroquiGraph, CroquiNode } from '../types/croquiGraph'

export interface LayoutOptions {
  direction?: 'left-to-right' | 'top-to-bottom'
}

export interface DiagramEngineAdapter {
  loadGraph(graph: CroquiGraph): Promise<void>
  applyAutoLayout(options?: LayoutOptions): Promise<void>
  getGraph(): CroquiGraph
  exportSvg(): Promise<string>
  undo(): void
  redo(): void
  selectElement(id: string): void
  updateHeader(header: CroquiGraph['header']): void
  updateElement(id: string, patch: Partial<unknown>): void
  deleteElement(id: string): void
  addNode(node: CroquiNode): void
  addEdge(edge: CroquiEdge): void
}

export interface DiagramEngineEvents {
  onGraphChange?: (graph: CroquiGraph) => void
  onSelect?: (id: string) => void
}
