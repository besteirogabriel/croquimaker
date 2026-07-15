declare module 'yfiles' {
  export const GraphComponent: unknown
  export const HierarchicLayout: unknown
  export const OrganicLayout: unknown
  export const OrthogonalLayout: unknown
  export const OrthogonalEdgeRouter: unknown
}

declare module 'elkjs/lib/elk.bundled.js' {
  export default class ELK {
    layout(graph: unknown): Promise<unknown>
  }
}
