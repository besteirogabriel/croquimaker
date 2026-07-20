import type { CroquiEdge, CroquiGraph, CroquiNode } from '../../types/croquiGraph'
import type { DiagramEngineAdapter, DiagramEngineEvents, LayoutOptions } from '../DiagramEngineAdapter'
import { FallbackSvgDiagramEngine } from '../fallback/FallbackSvgDiagramEngine'

export class YFilesDiagramEngine implements DiagramEngineAdapter {
  private readonly fallback: FallbackSvgDiagramEngine
  private yfilesLoaded = false

  constructor(host: HTMLElement, events: DiagramEngineEvents = {}) {
    this.fallback = new FallbackSvgDiagramEngine(host, events)
  }

  async loadGraph(graph: CroquiGraph): Promise<void> {
    await this.ensureYFiles()
    await this.fallback.loadGraph(graph)
  }

  async applyAutoLayout(options?: LayoutOptions): Promise<void> {
    await this.fallback.applyAutoLayout(options)
  }

  getGraph(): CroquiGraph {
    return this.fallback.getGraph()
  }

  async exportSvg(): Promise<string> {
    return this.fallback.exportSvg()
  }

  undo(): void {
    this.fallback.undo()
  }

  redo(): void {
    this.fallback.redo()
  }

  selectElement(id: string): void {
    this.fallback.selectElement(id)
  }

  updateHeader(header: CroquiGraph['header']): void {
    this.fallback.updateHeader(header)
  }

  updateElement(id: string, patch: Partial<unknown>): void {
    this.fallback.updateElement(id, patch)
  }

  deleteElement(id: string): void {
    this.fallback.deleteElement(id)
  }

  addNode(node: CroquiNode): void {
    this.fallback.addNode(node)
  }

  addEdge(edge: CroquiEdge): void {
    this.fallback.addEdge(edge)
  }

  private async ensureYFiles(): Promise<void> {
    if (this.yfilesLoaded) return
    try {
      const loadYFiles = new Function('return import("yfiles")') as () => Promise<unknown>
      await loadYFiles()
      this.yfilesLoaded = true
      // The fallback remains active until the proprietary yFiles package and license
      // are installed. This class is the integration boundary for GraphComponent,
      // OrthogonalLayout, HierarchicLayout, OrthogonalEdgeRouter, and SVG export.
    } catch {
      this.yfilesLoaded = false
    }
  }
}
