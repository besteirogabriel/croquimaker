import React from 'react'
import { createRoot } from 'react-dom/client'
import { CroquiEditorPage } from './pages/CroquiEditorPage'
import './styles.css'

createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <CroquiEditorPage />
  </React.StrictMode>
)
