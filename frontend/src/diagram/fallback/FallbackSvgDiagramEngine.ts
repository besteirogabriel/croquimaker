import type { DiagramEngineAdapter, DiagramEngineEvents, LayoutOptions } from '../DiagramEngineAdapter'
import type { CroquiEdge, CroquiGraph, CroquiNode, CroquiWorkZone } from '../../types/croquiGraph'

const PAGE_W = 1120
const PAGE_H = 760
const DRAWING = { x: 36, y: 112, w: 1048, h: 482 }

export class FallbackSvgDiagramEngine implements DiagramEngineAdapter {
  private graph: CroquiGraph | null = null
  private selectedId = ''

  constructor(
    private readonly host: HTMLElement,
    private readonly events: DiagramEngineEvents = {}
  ) {}

  async loadGraph(graph: CroquiGraph): Promise<void> {
    this.graph = cloneGraph(graph)
    await this.applyAutoLayout()
  }

  async applyAutoLayout(options?: LayoutOptions): Promise<void> {
    if (!this.graph) return
    if (!(await this.tryElkLayout(options))) {
      this.applyDeterministicLayout(options)
    }
    this.positionWorkZones()
    this.render()
    this.emitChange()
  }

  getGraph(): CroquiGraph {
    if (!this.graph) throw new Error('Graph not loaded')
    return cloneGraph(this.graph)
  }

  async exportSvg(): Promise<string> {
    this.render()
    return this.host.querySelector('svg')?.outerHTML ?? ''
  }

  selectElement(id: string): void {
    this.selectedId = id
    this.render()
    this.events.onSelect?.(id)
  }

  updateElement(id: string, patch: Partial<unknown>): void {
    if (!this.graph) return
    const node = this.graph.nodes.find((item) => item.id === id)
    const edge = this.graph.edges.find((item) => item.id === id)
    const label = this.graph.labels.find((item) => item.id === id)
    const zone = this.graph.workZones.find((item) => item.id === id)
    Object.assign(node ?? edge ?? label ?? zone ?? {}, patch)
    this.syncMainEquipment()
    this.render()
    this.emitChange()
  }

  deleteElement(id: string): void {
    if (!this.graph) return
    this.graph.nodes = this.graph.nodes.filter((item) => item.id !== id)
    this.graph.edges = this.graph.edges.filter((item) => item.id !== id && item.source !== id && item.target !== id)
    this.graph.labels = this.graph.labels.filter((item) => item.id !== id && item.attachedTo !== id)
    this.graph.workZones = this.graph.workZones.filter((item) => item.id !== id && item.attachedTo !== id)
    if (this.selectedId === id) this.selectedId = ''
    this.render()
    this.emitChange()
  }

  addNode(node: CroquiNode): void {
    if (!this.graph) return
    this.graph.nodes.push({ ...node, x: node.x ?? 180, y: node.y ?? 260, width: node.width ?? 56, height: node.height ?? 32 })
    this.graph.labels.push({ id: `LBL-${node.id}`, text: node.code || node.id, attachedTo: node.id, kind: 'code' })
    this.render()
    this.emitChange()
  }

  addEdge(edge: CroquiEdge): void {
    if (!this.graph) return
    this.graph.edges.push(edge)
    this.render()
    this.emitChange()
  }

  private async tryElkLayout(options?: LayoutOptions): Promise<boolean> {
    if (!this.graph || this.graph.nodes.length === 0) return false
    try {
      const { default: ELK } = await import('elkjs/lib/elk.bundled.js')
      const elk = new ELK()
      const result = (await elk.layout({
        id: 'croqui',
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': options?.direction === 'top-to-bottom' ? 'DOWN' : 'RIGHT',
          'elk.edgeRouting': 'ORTHOGONAL',
          'elk.spacing.nodeNode': '70',
          'elk.layered.spacing.nodeNodeBetweenLayers': '120'
        },
        children: this.graph.nodes.map((node) => ({ id: node.id, width: node.width ?? 56, height: node.height ?? 32 })),
        edges: this.graph.edges.map((edge) => ({ id: edge.id, sources: [edge.source], targets: [edge.target] }))
      })) as { children?: Array<{ id: string; x?: number; y?: number }> }
      const children = result.children ?? []
      for (const child of children) {
        const node = this.graph.nodes.find((item) => item.id === child.id)
        if (!node) continue
        node.x = DRAWING.x + 80 + Number(child.x ?? 0)
        node.y = DRAWING.y + 80 + Number(child.y ?? 0)
      }
      normalizePositions(this.graph.nodes)
      return true
    } catch {
      return false
    }
  }

  private applyDeterministicLayout(options?: LayoutOptions): void {
    if (!this.graph) return
    const mainId = this.graph.mainEquipment.id
    const nodes = [...this.graph.nodes]
    const main = nodes.find((node) => node.id === mainId || node.isMain) ?? nodes[0]
    const others = nodes.filter((node) => node.id !== main?.id)
    const horizontal = options?.direction !== 'top-to-bottom'
    if (main) {
      main.x = DRAWING.x + DRAWING.w * 0.5
      main.y = DRAWING.y + DRAWING.h * 0.48
      main.isMain = true
    }
    const left = others.slice(0, Math.ceil(others.length / 2))
    const right = others.slice(Math.ceil(others.length / 2))
    const place = (items: CroquiNode[], side: -1 | 1) => {
      const gap = horizontal ? 118 : 86
      items.forEach((node, index) => {
        const offset = (index + 1) * gap
        node.x = horizontal ? (main?.x ?? 560) + side * offset : (main?.x ?? 560) + side * 160
        node.y = horizontal ? (main?.y ?? 330) + ((index % 3) - 1) * 76 : (main?.y ?? 330) + side * offset
      })
    }
    place(left.reverse(), -1)
    place(right, 1)
    normalizePositions(this.graph.nodes)
  }

  private positionWorkZones(): void {
    if (!this.graph) return
    for (const zone of this.graph.workZones) {
      const node = this.graph.nodes.find((item) => item.id === zone.attachedTo || item.isMain)
      zone.width = zone.width ?? 130
      zone.height = zone.height ?? 76
      if (!node) continue
      zone.x = zone.x ?? Number(node.x ?? DRAWING.x + DRAWING.w / 2) + 28
      zone.y = zone.y ?? Number(node.y ?? DRAWING.y + DRAWING.h / 2) - 18
    }
  }

  private syncMainEquipment(): void {
    if (!this.graph) return
    const main = this.graph.nodes.find((item) => item.id === this.graph?.mainEquipment.id || item.isMain)
    if (!main) return
    this.graph.nodes.forEach((item) => {
      item.isMain = item.id === main.id
    })
    this.graph.mainEquipment.id = main.id
    this.graph.mainEquipment.type = main.equipmentType || this.graph.mainEquipment.type
    this.graph.mainEquipment.code = main.code || this.graph.mainEquipment.code
    this.graph.header.equipamento = `${this.graph.mainEquipment.type} ${this.graph.mainEquipment.code}`.trim()
  }

  private render(): void {
    if (!this.graph) {
      this.host.innerHTML = ''
      return
    }
    this.host.innerHTML = buildSvg(this.graph, this.selectedId)
    this.attachDragHandlers()
  }

  private attachDragHandlers(): void {
    if (!this.graph) return
    const svg = this.host.querySelector('svg')
    if (!svg) return
    for (const element of Array.from(svg.querySelectorAll<SVGGElement>('[data-node-id]'))) {
      element.addEventListener('pointerdown', (event) => this.beginDrag(event, element.dataset.nodeId ?? '', 'node'))
    }
    for (const element of Array.from(svg.querySelectorAll<SVGGElement>('[data-work-zone-id]'))) {
      element.addEventListener('pointerdown', (event) => this.beginDrag(event, element.dataset.workZoneId ?? '', 'zone'))
    }
  }

  private beginDrag(event: PointerEvent, id: string, kind: 'node' | 'zone'): void {
    if (!this.graph || !id) return
    event.preventDefault()
    this.selectElement(id)
    const start = svgPoint(this.host, event)
    const target = kind === 'node'
      ? this.graph.nodes.find((item) => item.id === id)
      : this.graph.workZones.find((item) => item.id === id)
    if (!target) return
    const startX = Number(target.x ?? 0)
    const startY = Number(target.y ?? 0)
    const move = (moveEvent: PointerEvent) => {
      const point = svgPoint(this.host, moveEvent)
      target.x = startX + point.x - start.x
      target.y = startY + point.y - start.y
      this.render()
      this.emitChange()
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  private emitChange(): void {
    if (this.graph) this.events.onGraphChange?.(cloneGraph(this.graph))
  }
}

function buildSvg(graph: CroquiGraph, selectedId: string): string {
  const nodes = graph.nodes.map((node) => nodeSvg(node, selectedId)).join('')
  const edges = graph.edges.map((edge) => edgeSvg(edge, graph.nodes)).join('')
  const zones = graph.workZones.map((zone) => workZoneSvg(zone, selectedId)).join('')
  const labels = graph.labels.map((label) => labelSvg(label, graph.nodes)).join('')
  const warnings = [...graph.validation.blockingErrors, ...graph.validation.warnings]
    .map((item) => escapeXml(String(item.code ?? item.message ?? 'warning')))
    .join(' | ')
  return `
  <svg xmlns="http://www.w3.org/2000/svg" width="${PAGE_W}" height="${PAGE_H}" viewBox="0 0 ${PAGE_W} ${PAGE_H}" role="img">
    <rect x="0" y="0" width="${PAGE_W}" height="${PAGE_H}" fill="#fff"/>
    <rect x="22" y="26" width="${PAGE_W - 44}" height="${PAGE_H - 52}" fill="#fff" stroke="#161616" stroke-width="1.4"/>
    <text x="${PAGE_W / 2}" y="46" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="700">Croqui</text>
    <text x="42" y="84" font-family="Arial, sans-serif" font-size="32" font-weight="700" font-style="italic">RGE</text>
    ${headerSvg(graph)}
    <rect x="${DRAWING.x}" y="${DRAWING.y}" width="${DRAWING.w}" height="${DRAWING.h}" fill="#fff" stroke="#111" stroke-width="0.7"/>
    <g data-layer="edges">${edges}</g>
    <g data-layer="work-zones">${zones}</g>
    <g data-layer="nodes">${nodes}</g>
    <g data-layer="labels">${labels}</g>
    <text x="42" y="618" font-family="Arial, sans-serif" font-size="12" font-weight="700">Validação: ${escapeXml(graph.validation.status)}</text>
    <text x="42" y="640" font-family="Arial, sans-serif" font-size="10">${warnings}</text>
  </svg>`
}

function headerSvg(graph: CroquiGraph): string {
  const fields = [
    ['Departamento:', graph.header.departamento, 42, 94, 174],
    ['Município:', graph.header.municipio, 340, 94, 210],
    ['Equipamento:', graph.header.equipamento, 706, 94, 190],
    ['Data do Levantamento:', graph.header.data_levantamento, 42, 108, 174],
    ['Responsável:', graph.header.responsavel, 340, 108, 330]
  ] as const
  return `
    <rect x="36" y="70" width="1048" height="36" fill="#fff" stroke="#111" stroke-width="0.7"/>
    <line x1="36" y1="88" x2="1084" y2="88" stroke="#111" stroke-width="0.55"/>
    ${fields.map(([label, value, x, y, w]) => `
      <text x="${x}" y="${y - 5}" font-family="Arial, sans-serif" font-size="8" font-weight="700">${escapeXml(label)}</text>
      <text x="${x + w}" y="${y - 5}" text-anchor="middle" font-family="Arial, sans-serif" font-size="8">${escapeXml(value)}</text>
    `).join('')}`
}

function edgeSvg(edge: CroquiEdge, nodes: CroquiNode[]): string {
  const source = nodes.find((node) => node.id === edge.source)
  const target = nodes.find((node) => node.id === edge.target)
  if (!source || !target) return ''
  const sx = Number(source.x ?? 0)
  const sy = Number(source.y ?? 0)
  const tx = Number(target.x ?? 0)
  const ty = Number(target.y ?? 0)
  const midX = (sx + tx) / 2
  const points = `${sx},${sy} ${midX},${sy} ${midX},${ty} ${tx},${ty}`
  const dash = edge.style === 'dashed' ? 'stroke-dasharray="8 7"' : ''
  return `<polyline points="${points}" fill="none" stroke="#32363a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ${dash}/>`
}

function nodeSvg(node: CroquiNode, selectedId: string): string {
  const x = Number(node.x ?? 0)
  const y = Number(node.y ?? 0)
  const selected = node.id === selectedId
  const focus = node.isMain ? `<circle cx="${x}" cy="${y}" r="28" fill="none" stroke="#d71920" stroke-width="2" stroke-dasharray="6 5"/>` : ''
  const ring = selected ? `<circle cx="${x}" cy="${y}" r="34" fill="none" stroke="#0b64c0" stroke-width="2"/>` : ''
  let symbol = `<circle cx="${x}" cy="${y}" r="9" fill="#fff" stroke="#111" stroke-width="2"/>`
  if (node.kind === 'transformer') {
    symbol = `<rect x="${x - 20}" y="${y - 14}" width="40" height="28" rx="3" fill="#fff" stroke="#111" stroke-width="2"/>
      <circle cx="${x - 7}" cy="${y}" r="7" fill="none" stroke="#111"/>
      <circle cx="${x + 7}" cy="${y}" r="7" fill="none" stroke="#111"/>`
  } else if (node.kind === 'switch' || node.kind === 'equipment') {
    symbol = `<line x1="${x - 22}" y1="${y}" x2="${x + 22}" y2="${y}" stroke="#111" stroke-width="2.4"/>
      <line x1="${x - 4}" y1="${y}" x2="${x + 13}" y2="${y - 13}" stroke="#111" stroke-width="2"/>
      <circle cx="${x - 22}" cy="${y}" r="3" fill="#111"/>
      <circle cx="${x + 22}" cy="${y}" r="3" fill="#111"/>`
  }
  return `<g data-node-id="${escapeXml(node.id)}" style="cursor:grab">${focus}${ring}${symbol}</g>`
}

function labelSvg(label: { id: string; text: string; attachedTo: string }, nodes: CroquiNode[]): string {
  const node = nodes.find((item) => item.id === label.attachedTo)
  const x = Number(node?.x ?? 0) + 12
  const y = Number(node?.y ?? 0) - 18
  return `<text data-label-id="${escapeXml(label.id)}" x="${x}" y="${y}" font-family="Arial, sans-serif" font-size="12">${escapeXml(label.text)}</text>`
}

function workZoneSvg(zone: CroquiWorkZone, selectedId: string): string {
  const x = Number(zone.x ?? 0)
  const y = Number(zone.y ?? 0)
  const w = Number(zone.width ?? 130)
  const h = Number(zone.height ?? 76)
  const selected = zone.id === selectedId ? '#0b64c0' : '#d71920'
  return `<g data-work-zone-id="${escapeXml(zone.id)}" transform="translate(${x} ${y}) rotate(-12)" style="cursor:move">
    <rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="none" stroke="${selected}" stroke-width="2" stroke-dasharray="8 6"/>
    <line x1="-28" y1="0" x2="28" y2="0" stroke="#d71920" stroke-width="2"/>
    <line x1="12" y1="-8" x2="28" y2="0" stroke="#d71920" stroke-width="2"/>
    <line x1="12" y1="8" x2="28" y2="0" stroke="#d71920" stroke-width="2"/>
  </g>`
}

function normalizePositions(nodes: CroquiNode[]): void {
  const xs = nodes.map((node) => Number(node.x ?? DRAWING.x + DRAWING.w / 2))
  const ys = nodes.map((node) => Number(node.y ?? DRAWING.y + DRAWING.h / 2))
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const usedW = Math.max(maxX - minX, 1)
  const usedH = Math.max(maxY - minY, 1)
  const scale = Math.min((DRAWING.w - 120) / usedW, (DRAWING.h - 120) / usedH, 1.7)
  for (const node of nodes) {
    node.x = DRAWING.x + 60 + (Number(node.x ?? minX) - minX) * scale
    node.y = DRAWING.y + 60 + (Number(node.y ?? minY) - minY) * scale
  }
}

function svgPoint(host: HTMLElement, event: PointerEvent): { x: number; y: number } {
  const svg = host.querySelector('svg')
  if (!svg) return { x: 0, y: 0 }
  const rect = svg.getBoundingClientRect()
  return {
    x: ((event.clientX - rect.left) / rect.width) * PAGE_W,
    y: ((event.clientY - rect.top) / rect.height) * PAGE_H
  }
}

function cloneGraph(graph: CroquiGraph): CroquiGraph {
  return JSON.parse(JSON.stringify(graph)) as CroquiGraph
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
