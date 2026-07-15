import { useRef, useState } from 'react'

interface Props {
  disabled: boolean
  onUpload: (file: File) => void
}

export function UploadPanel({ disabled, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [name, setName] = useState('')

  function submit() {
    const file = inputRef.current?.files?.[0]
    if (file) onUpload(file)
  }

  return (
    <section className="panel">
      <div className="panel-title">Upload</div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        disabled={disabled}
        onChange={(event) => setName(event.target.files?.[0]?.name ?? '')}
      />
      <button onClick={submit} disabled={disabled || !name}>Extrair graph</button>
      {name && <div className="muted">{name}</div>}
    </section>
  )
}
