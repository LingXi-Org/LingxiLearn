'use client'

import { useCallback, useEffect, useId, useRef, useState } from 'react'
import type { Artifact } from '@/entities/artifact/model'
import { artifactApi } from '@/shared/api/client'
import { EmptyState, ErrorState, LoadingState } from '@/shared/ui/async-state'

export function ArtifactLibrary({ workspaceId }: { workspaceId: string }) {
  const [artifacts, setArtifacts] = useState<Artifact[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const uploadId = useId()

  const load = useCallback(async () => {
    try {
      const response = await artifactApi.list(workspaceId)
      setArtifacts(response.artifacts ?? [])
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load artifacts')
    }
  }, [workspaceId])

  useEffect(() => void load(), [load])

  async function upload(file: File | undefined) {
    if (!file) return
    try {
      await artifactApi.upload(workspaceId, file)
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Upload failed')
    } finally {
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  async function rename(artifact: Artifact) {
    const name = window.prompt('Artifact name', artifact.name)?.trim()
    if (!name || name === artifact.name) return
    await artifactApi.rename(workspaceId, artifact.id, name)
    await load()
  }

  async function remove(artifact: Artifact) {
    if (!window.confirm(`Delete “${artifact.name}”?`)) return
    await artifactApi.remove(workspaceId, artifact.id)
    await load()
  }

  return (
    <div className='stack-lg'>
      <div className='section-actions'>
        <div>
          <span className='eyebrow'>Artifact library</span>
          <h1>Learning, made tangible.</h1>
        </div>
        <label className='button primary' htmlFor={uploadId}>
          Upload artifact
        </label>
        <input
          hidden
          id={uploadId}
          ref={fileInput}
          type='file'
          onChange={(event) => void upload(event.target.files?.[0])}
        />
      </div>
      {error && <ErrorState message={error} />}
      {artifacts === null ? (
        <LoadingState />
      ) : artifacts.length === 0 ? (
        <EmptyState
          title='No artifacts yet'
          description='Upload a source or let an agent task create one.'
        />
      ) : (
        <div className='card-grid'>
          {artifacts.map((artifact) => (
            <article className='data-card' key={artifact.id}>
              <div className='card-heading'>
                <span className='file-mark'>{artifact.kind ?? 'file'}</span>
                <span>{artifact.source}</span>
              </div>
              <h2>{artifact.name}</h2>
              <p>
                {artifact.mimeType} · {formatBytes(artifact.size)}
              </p>
              <div className='card-actions'>
                <a href={artifactApi.contentUrl(workspaceId, artifact.id)}>Download</a>
                <button type='button' onClick={() => void rename(artifact)}>
                  Rename
                </button>
                <button className='danger-link' type='button' onClick={() => void remove(artifact)}>
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
