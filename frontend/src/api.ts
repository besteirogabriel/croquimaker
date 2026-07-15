import type { CroquiGraph, ExportResponse } from './types/croquiGraph'

export interface SessionResponse {
  authenticated: boolean
  user: { email: string; name: string; role: string; city_group: string } | null
}

export async function getSession(): Promise<SessionResponse> {
  const response = await fetch('/api/auth/session', { credentials: 'include' })
  return response.json()
}

export async function login(email: string, password: string): Promise<SessionResponse> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  if (!response.ok) throw new Error('Credenciais invalidas.')
  const data = await response.json()
  return { authenticated: true, user: data.user }
}

export async function uploadProject(pdf: File): Promise<{ job_id: string; graph: CroquiGraph }> {
  const form = new FormData()
  form.append('pdf', pdf)
  const response = await fetch('/api/projects/upload', {
    method: 'POST',
    credentials: 'include',
    body: form
  })
  const data = await response.json()
  if (!response.ok || !data.ok) throw new Error(data.error || 'Falha no upload.')
  return { job_id: data.job_id, graph: data.graph as CroquiGraph }
}

export async function exportProject(jobId: string, graph: CroquiGraph, svg: string): Promise<ExportResponse> {
  const response = await fetch(`/api/projects/${jobId}/export`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ graph, svg })
  })
  const data = await response.json()
  if (!response.ok || !data.ok) throw new Error(data.error || 'Falha na exportacao.')
  return data as ExportResponse
}
