export type EquipmentType = 'TR' | 'FU' | 'FC' | 'RL' | 'RG' | 'OL' | 'SC' | ''
export type CroquiNodeKind = 'pole' | 'equipment' | 'transformer' | 'switch' | 'junction'
export type CroquiNetworkType = 'AT' | 'BT' | 'AT_BT' | 'UNKNOWN'
export type CroquiEdgeStyle = 'solid' | 'dashed'
export type CroquiLabelKind = 'code' | 'network' | 'note' | 'kva'
export type CroquiValidationStatus = 'draft' | 'final_candidate' | 'blocked'

export interface CroquiHeader {
  departamento: string
  municipio: string
  equipamento: string
  data_levantamento: string
  responsavel: string
}

export interface CroquiMainEquipment {
  id: string
  type: EquipmentType | string
  code: string
  confidence: number
  evidence: Record<string, unknown>[]
}

export interface CroquiNode {
  id: string
  kind: CroquiNodeKind
  code: string
  equipmentType: EquipmentType | string
  isMain: boolean
  sourceBbox: number[]
  confidence: number
  x?: number | null
  y?: number | null
  width?: number | null
  height?: number | null
}

export interface CroquiEdge {
  id: string
  source: string
  target: string
  networkType: CroquiNetworkType
  style: CroquiEdgeStyle
  confidence: number
}

export interface CroquiLabel {
  id: string
  text: string
  attachedTo: string
  kind: CroquiLabelKind
  x?: number | null
  y?: number | null
}

export interface CroquiWorkZone {
  id: string
  kind: 'red_dashed_rectangle'
  attachedTo: string
  confidence: number
  x?: number | null
  y?: number | null
  width?: number | null
  height?: number | null
}

export interface CroquiValidation {
  status: CroquiValidationStatus
  warnings: Record<string, unknown>[]
  blockingErrors: Record<string, unknown>[]
}

export interface CroquiGraph {
  id: string
  header: CroquiHeader
  mainEquipment: CroquiMainEquipment
  nodes: CroquiNode[]
  edges: CroquiEdge[]
  labels: CroquiLabel[]
  workZones: CroquiWorkZone[]
  validation: CroquiValidation
}

export interface ExportResponse {
  ok: boolean
  outputs: Record<string, string>
  validation_report: unknown
  artifacts: Array<{ kind: string; label: string; download_url: string }>
  revision?: number
}
