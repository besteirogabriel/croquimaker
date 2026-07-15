import type { DiagramEngineAdapter, DiagramEngineEvents } from './DiagramEngineAdapter'
import { YFilesDiagramEngine } from './yfiles/YFilesDiagramEngine'

export function createDiagramEngine(host: HTMLElement, events: DiagramEngineEvents): DiagramEngineAdapter {
  return new YFilesDiagramEngine(host, events)
}
