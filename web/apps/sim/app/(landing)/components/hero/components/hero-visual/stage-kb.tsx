import type { CSSProperties, RefObject } from 'react'
import { cn } from '@sim/emcn'
import { Upload, X } from '@sim/emcn/icons'
import { KnowledgeGraphMiniSvg } from '@/lib/lingxi/components/knowledge-graph-canvas'
import {
  GRAPH_EDGES,
  GRAPH_NODES,
  GRAPH_VIEWBOX,
  KB_FILES,
  KB_NAME,
} from '@/app/(landing)/components/hero/components/hero-visual/workflow-data'

/** Which beat of the knowledge-base flow the modal is showing. */
export type KbStage = 'empty' | 'files' | 'embeddings'

interface KnowledgeBasePanelProps {
  stage: KbStage
  /** The Create button - the root cursor targets this to "create". */
  createRef: RefObject<HTMLSpanElement | null>
  /**
   * `modal` renders the standalone centered modal (its own chrome + entrance);
   * `morph` renders the content only, filling its host, so a satellite block can
   * morph into it in scene space.
   */
  motion?: 'modal' | 'morph'
}

/**
 * The knowledge-base create UI - a faithful, decorative replica of the real
 * `ChipModal` create flow. First an empty dropzone ("Drop files here"); then
 * files drop in from above as if dragged from Finder; then the document area
 * becomes an embedding map that builds itself node by node while the footer
 * reads "Creating…". The Create button is exposed as a cursor target.
 */
export function KnowledgeBasePanel({
  stage,
  createRef,
  motion = 'modal',
}: KnowledgeBasePanelProps) {
  const creating = stage === 'embeddings'

  const content = (
    <div
      className={cn(
        'overflow-hidden rounded-lg border border-[var(--border-1)] bg-[var(--bg)]',
        motion === 'morph' && 'h-full'
      )}
    >
      <div className='flex items-center justify-between px-4 pt-3 pb-2.5'>
        <span className='font-medium text-[15px] text-[var(--text-primary)]'>创建知识库</span>
        <X className='size-4 text-[var(--text-muted)]' />
      </div>

      <div className='flex flex-col gap-4 px-4 pb-4'>
        <div className='flex flex-col gap-[9px]'>
          <span className='text-[13px] text-[var(--text-muted)]'>名称</span>
          <div className='flex h-[30px] items-center rounded-lg border border-[var(--border-1)] bg-[var(--surface-5)] px-2 text-[14px] text-[var(--text-body)]'>
            {KB_NAME}
          </div>
        </div>

        <div className='flex flex-col gap-[9px]'>
          <span className='text-[13px] text-[var(--text-muted)]'>
            {creating ? '向量嵌入' : '上传文档'}
          </span>
          <div className='relative h-[188px]'>
            {stage === 'empty' && (
              <div className='absolute inset-0 flex flex-col items-center justify-center gap-1 rounded-lg border border-[var(--border-1)] border-dashed bg-[var(--surface-5)] text-center'>
                <Upload className='size-5 text-[var(--text-muted)]' />
                <span className='text-[var(--text-primary)] text-caption'>将文件拖到此处</span>
                <span className='text-[var(--text-tertiary)] text-xs'>PDF, DOCX, TXT, CSV, MD</span>
              </div>
            )}

            {stage === 'files' && (
              <div className='absolute inset-0 flex flex-col justify-center gap-2'>
                {KB_FILES.map((file, i) => (
                  <div
                    key={file.name}
                    className={cn(
                      'flex items-center gap-2 rounded-lg border border-[var(--border-1)] bg-[var(--surface-5)] p-2',
                      'animate-hero-file-drop opacity-0 [animation-delay:var(--drop-delay)] motion-reduce:animate-none motion-reduce:opacity-100'
                    )}
                    style={{ '--drop-delay': `${120 + i * 170}ms` } as CSSProperties}
                  >
                    <file.icon className='size-[14px] flex-shrink-0 text-[var(--text-icon)]' />
                    <span className='min-w-0 flex-1 truncate text-[14px] text-[var(--text-body)]'>
                      {file.name}
                    </span>
                    <span className='flex-shrink-0 text-[14px] text-[var(--text-muted)]'>
                      {file.size}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {creating && (
              <div className='absolute inset-0 flex flex-col items-center justify-center gap-1.5 rounded-lg border border-[var(--border-1)] bg-[var(--surface-5)] px-3'>
                <KnowledgeGraphMiniSvg
                  viewBox={GRAPH_VIEWBOX}
                  nodes={GRAPH_NODES}
                  edges={GRAPH_EDGES}
                />
                <span className='text-[var(--text-muted)] text-caption'>正在生成向量…</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className='flex items-center justify-end gap-2 rounded-b-lg bg-[var(--surface-3)] px-4 pt-2 pb-2'>
        <span className='flex h-[30px] items-center rounded-lg px-2 text-[14px] text-[var(--text-body)]'>
          取消
        </span>
        <span
          ref={createRef}
          className='flex h-[30px] items-center rounded-lg bg-[var(--text-primary)] px-2 text-[14px] text-[var(--text-inverse)]'
        >
          {creating ? '创建中…' : '创建'}
        </span>
      </div>
    </div>
  )

  if (motion === 'morph') {
    return (
      <div className='h-full w-full animate-hero-kb-content-morph opacity-0 motion-reduce:animate-none motion-reduce:opacity-100'>
        {content}
      </div>
    )
  }

  return (
    <div
      className={cn(
        'w-full max-w-[420px] rounded-xl border border-[var(--border-muted)] bg-[var(--surface-4)] p-[3px] shadow-[var(--shadow-overlay)]',
        'animate-hero-modal-in motion-reduce:animate-none'
      )}
    >
      {content}
    </div>
  )
}
