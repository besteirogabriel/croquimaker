import { useEffect, useRef, useState } from 'react'
import { exportProject, getSession, login, uploadProject } from '../api'
import { DiagramCanvas, type DiagramCanvasHandle } from '../ui/DiagramCanvas'
import { ExportPanel } from '../ui/ExportPanel'
import { PropertiesPanel } from '../ui/PropertiesPanel'
import { UploadPanel } from '../ui/UploadPanel'
import { ValidationPanel } from '../ui/ValidationPanel'
import type { CroquiEdge, CroquiGraph, CroquiNode, ExportResponse } from '../types/croquiGraph'

export function CroquiEditorPage() {
  const [authenticated, setAuthenticated] = useState(false)
  const [email, setEmail] = useState('admin@jobel.local')
  const [password, setPassword] = useState('Jobel@2026!')
  const [jobId, setJobId] = useState('')
  const [graph, setGraph] = useState<CroquiGraph | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null)
  const canvasRef = useRef<DiagramCanvasHandle>(null)

  useEffect(() => {
    getSession().then((session) => setAuthenticated(session.authenticated)).catch(() => setAuthenticated(false))
  }, [])

  async function handleLogin() {
    setBusy(true)
    setMessage('')
    try {
      await login(email, password)
      setAuthenticated(true)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Falha no login.')
    } finally {
      setBusy(false)
    }
  }

  async function handleUpload(file: File) {
    setBusy(true)
    setMessage('Extraindo CroquiGraph no backend Python...')
    setExportResult(null)
    try {
      const result = await uploadProject(file)
      setJobId(result.job_id)
      setGraph(result.graph)
      setSelectedId(result.graph.mainEquipment.id)
      setMessage('CroquiGraph carregado no editor.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Falha ao enviar PDF.')
    } finally {
      setBusy(false)
    }
  }

  async function handleLayout() {
    await canvasRef.current?.applyAutoLayout()
    setGraph(canvasRef.current?.getGraph() ?? graph)
  }

  async function handleExport() {
    if (!graph || !jobId) return
    setBusy(true)
    setMessage('Exportando PDF/XLS a partir do SVG do editor...')
    try {
      const latest = canvasRef.current?.getGraph() ?? graph
      const svg = (await canvasRef.current?.exportSvg()) ?? ''
      const result = await exportProject(jobId, latest, svg)
      setGraph(latest)
      setExportResult(result)
      setMessage('Exportacao concluida.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Falha na exportacao.')
    } finally {
      setBusy(false)
    }
  }

  function updateGraph(next: CroquiGraph) {
    setGraph(next)
  }

  function patchHeader(key: keyof CroquiGraph['header'], value: string) {
    if (!graph) return
    setGraph({ ...graph, header: { ...graph.header, [key]: value } })
  }

  function patchSelected(patch: Partial<Record<string, unknown>>) {
    if (!graph || !selectedId) return
    canvasRef.current?.updateElement(selectedId, patch)
    setGraph(canvasRef.current?.getGraph() ?? graph)
  }

  function addNode(kind: CroquiNode['kind']) {
    if (!graph) return
    const id = `${kind.toUpperCase()}-${Date.now().toString().slice(-5)}`
    const node: CroquiNode = {
      id,
      kind,
      code: kind === 'pole' ? id : '',
      equipmentType: kind === 'transformer' ? 'TR' : kind === 'switch' ? 'FU' : '',
      isMain: false,
      sourceBbox: [],
      confidence: 1,
      x: 240,
      y: 240,
      width: kind === 'pole' ? 18 : 56,
      height: kind === 'pole' ? 18 : 32
    }
    canvasRef.current?.addNode(node)
    setGraph(canvasRef.current?.getGraph() ?? graph)
    setSelectedId(id)
  }

  function addEdge(source: string, target: string) {
    if (!graph || !source || !target || source === target) return
    const edge: CroquiEdge = {
      id: `EDGE-${Date.now().toString().slice(-6)}`,
      source,
      target,
      networkType: 'UNKNOWN',
      style: 'solid',
      confidence: 1
    }
    canvasRef.current?.addEdge(edge)
    setGraph(canvasRef.current?.getGraph() ?? graph)
  }

  function deleteSelected() {
    if (!graph || !selectedId) return
    canvasRef.current?.deleteElement(selectedId)
    setGraph(canvasRef.current?.getGraph() ?? graph)
    setSelectedId('')
  }

  return (
    <main className="app-shell">
      <aside className="left-rail">
        <section className="panel compact">
          <div className="panel-title">Sessao</div>
          {authenticated ? (
            <div className="status-ok">Conectado</div>
          ) : (
            <div className="login-form">
              <input value={email} onChange={(event) => setEmail(event.target.value)} aria-label="email" />
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" aria-label="senha" />
              <button onClick={handleLogin} disabled={busy}>Entrar</button>
            </div>
          )}
        </section>
        <UploadPanel disabled={!authenticated || busy} onUpload={handleUpload} />
        {graph && (
          <PropertiesPanel
            graph={graph}
            selectedId={selectedId}
            onHeaderChange={patchHeader}
            onSelectedPatch={patchSelected}
            onAddNode={addNode}
            onAddEdge={addEdge}
            onDeleteSelected={deleteSelected}
          />
        )}
      </aside>

      <section className="workspace">
        <div className="toolbar">
          <div>
            <strong>{jobId ? `Projeto ${jobId}` : 'Novo projeto'}</strong>
            <span>{message}</span>
          </div>
          <button onClick={handleLayout} disabled={!graph || busy}>Auto-layout</button>
        </div>
        <DiagramCanvas
          ref={canvasRef}
          graph={graph}
          selectedId={selectedId}
          onGraphChange={updateGraph}
          onSelect={setSelectedId}
        />
      </section>

      <aside className="right-rail">
        <ValidationPanel graph={graph} />
        <ExportPanel disabled={!graph || busy} result={exportResult} onExport={handleExport} />
      </aside>
    </main>
  )
}
