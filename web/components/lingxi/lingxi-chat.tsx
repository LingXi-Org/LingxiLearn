'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui-kit'
import type {
  ContentBlock,
  ReasoningStep,
  ToolCallInfo,
  ToolCallStatus,
} from '@/lib/lingxi/chat-types'
import { LingxiArtifactResource } from '@/lib/lingxi/components/lingxi-artifact-resource'
import {
  type LingxiArtifactResourceDescriptor,
  useLingxiChat,
} from '@/lib/lingxi/hooks/use-lingxi-chat'
import { useLingxiIdentity } from '@/lib/lingxi/lingxi-identity-provider'
import { WorkflowsEditorLoop } from '@/app/(landing)/workflows/components/workflows-editor-loop'

function statusLabel(status: ToolCallStatus): string {
  if (status === 'executing') return '执行中'
  if (status === 'success') return '已完成'
  if (status === 'error') return '有错误'
  return '已停止'
}

function statusClass(status: ToolCallStatus): string {
  if (status === 'executing') return 'text-[var(--text-accent)]'
  if (status === 'success') return 'text-[var(--text-success)]'
  if (status === 'error') return 'text-[var(--text-error)]'
  return 'text-[var(--text-muted)]'
}

function ReasoningRow({ step }: { step: ReasoningStep }) {
  return (
    <details className='group rounded-xl border border-[var(--border)] bg-[var(--surface-2)]'>
      <summary className='flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[var(--text-secondary)] text-xs [&::-webkit-details-marker]:hidden'>
        <span className='flex size-4 items-center justify-center rounded-full border border-[var(--border-1)] text-[10px] transition-transform group-open:rotate-90'>
          ›
        </span>
        <span className='font-medium'>{step.title}</span>
        <span className='ml-auto text-[var(--text-muted)]'>
          {step.status === 'active' ? '进行中' : step.status === 'error' ? '需注意' : '已完成'}
        </span>
      </summary>
      <p className='border-[var(--border)] border-t px-3 py-2 text-[var(--text-muted)] text-xs leading-5'>
        {step.summary}
      </p>
    </details>
  )
}

function ToolCallRow({ call }: { call: ToolCallInfo }) {
  return (
    <details className='rounded-xl border border-[var(--border)] bg-[var(--surface-2)]'>
      <summary className='flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-xs [&::-webkit-details-marker]:hidden'>
        <span className='font-medium text-[var(--text-secondary)]'>
          {call.displayTitle || call.name}
        </span>
        <span className={`ml-auto ${statusClass(call.status)}`}>{statusLabel(call.status)}</span>
      </summary>
      {(call.params || call.result) && (
        <div className='space-y-2 border-[var(--border)] border-t px-3 py-2 text-[var(--text-muted)] text-[11px]'>
          {call.params && (
            <pre className='overflow-x-auto whitespace-pre-wrap break-words'>
              {JSON.stringify(call.params, null, 2)}
            </pre>
          )}
          {call.result?.error && <p className='text-[var(--text-error)]'>{call.result.error}</p>}
          {call.result && !call.result.error && <p>工具已返回安全摘要。</p>}
        </div>
      )}
    </details>
  )
}

function ThinkingAndTools({ blocks }: { blocks: ContentBlock[] }) {
  const visible = blocks.filter(
    (block) => block.type === 'thinking' || block.type === 'tool_call' || block.type === 'subagent'
  )
  if (visible.length === 0) return null
  return (
    <div className='mb-3 space-y-2'>
      {visible.map((block, index) => {
        if (block.type === 'thinking' && block.reasoningStep) {
          return (
            <ReasoningRow key={`thinking-${block.reasoningStep.id}`} step={block.reasoningStep} />
          )
        }
        if (block.type === 'tool_call' && block.toolCall) {
          return <ToolCallRow key={`tool-${block.toolCall.id}-${index}`} call={block.toolCall} />
        }
        if (block.type === 'subagent') {
          return (
            <div
              key={`agent-${block.spanId || index}`}
              className='flex items-center gap-2 rounded-xl border border-[var(--border)] px-3 py-2 text-[var(--text-muted)] text-xs'
            >
              <span className='size-1.5 rounded-full bg-[var(--brand-accent)]' />
              {block.subagent || block.content || 'LingxiGraph 子任务'}
            </div>
          )
        }
        return null
      })}
    </div>
  )
}

function ArtifactTabs({
  resources,
  activeResourceId,
  onSelect,
}: {
  resources: LingxiArtifactResourceDescriptor[]
  activeResourceId: string | null
  onSelect: (resource: LingxiArtifactResourceDescriptor) => void
}) {
  return (
    <div className='flex shrink-0 gap-1 overflow-x-auto border-[var(--border)] border-b px-3 pt-3'>
      {resources.map((resource) => (
        <button
          key={resource.id}
          type='button'
          className={`whitespace-nowrap rounded-t-lg px-3 py-2 text-xs transition-colors ${
            activeResourceId === resource.id
              ? 'bg-[var(--surface-2)] font-medium text-[var(--text-primary)]'
              : 'text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text-secondary)]'
          }`}
          onClick={() => onSelect(resource)}
        >
          {resource.title}
        </button>
      ))}
    </div>
  )
}

function ArtifactPanel({
  resource,
  resources,
  onSelect,
}: {
  resource: LingxiArtifactResourceDescriptor | null
  resources: LingxiArtifactResourceDescriptor[]
  onSelect: (resource: LingxiArtifactResourceDescriptor) => void
}) {
  if (!resource) return null
  return (
    <aside className='flex min-h-0 min-w-0 flex-1 flex-col border-[var(--border)] border-l bg-[var(--surface-1)] lg:max-w-[560px]'>
      <div className='flex h-12 shrink-0 items-center justify-between border-[var(--border)] border-b px-4'>
        <div>
          <p className='font-medium text-[var(--text-primary)] text-sm'>学习产物</p>
          <p className='text-[var(--text-muted)] text-[11px]'>LingxiGraph 生成结果</p>
        </div>
        <span className='rounded-full bg-[var(--surface-3)] px-2 py-1 text-[10px] text-[var(--text-muted)]'>
          任务产物
        </span>
      </div>
      <ArtifactTabs resources={resources} activeResourceId={resource.id} onSelect={onSelect} />
      <div className='min-h-0 flex-1'>
        <LingxiArtifactResource resourceId={resource.id} />
      </div>
    </aside>
  )
}

export function LingxiChat({ workspaceId, taskId }: { workspaceId: string; taskId?: string }) {
  const identity = useLingxiIdentity()
  const chat = useLingxiChat(workspaceId, taskId)
  const [draft, setDraft] = useState('')
  const [activeResourceId, setActiveResourceId] = useState<string | null>(null)

  useEffect(() => {
    if (!activeResourceId && chat.resources.length > 0) {
      setActiveResourceId(chat.resources[0].id)
      return
    }
    if (activeResourceId && !chat.resources.some((resource) => resource.id === activeResourceId)) {
      setActiveResourceId(chat.resources[0]?.id ?? null)
    }
  }, [activeResourceId, chat.resources])

  const activeResource = useMemo(
    () => chat.resources.find((resource) => resource.id === activeResourceId) ?? null,
    [activeResourceId, chat.resources]
  )

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const message = draft.trim()
    if (!message) return
    setDraft('')
    await chat.sendMessage(message)
  }

  return (
    <main className='flex h-dvh min-h-0 flex-col bg-[var(--bg)] text-[var(--text-body)]'>
      <header className='flex h-12 shrink-0 items-center justify-between border-[var(--border)] border-b bg-[var(--surface-1)] px-4'>
        <div className='flex items-center gap-3'>
          <div className='flex size-7 items-center justify-center rounded-lg bg-[var(--text-primary)] font-semibold text-[var(--text-inverse)] text-xs'>
            灵
          </div>
          <div>
            <p className='font-medium text-[var(--text-primary)] text-sm'>灵犀智学</p>
            <p className='text-[var(--text-muted)] text-[10px]'>LingxiGraph 学习工作台</p>
          </div>
        </div>
        <div className='flex items-center gap-2'>
          {identity.user && (
            <span className='hidden max-w-40 truncate text-[var(--text-muted)] text-xs sm:block'>
              {identity.user.name || identity.user.email || identity.user.id}
            </span>
          )}
          {identity.configured && identity.client && !identity.authenticated && (
            <Button variant='outline' size='sm' onClick={() => void identity.client?.login()}>
              登录
            </Button>
          )}
          {identity.authenticated && identity.client && (
            <>
              <Button
                variant='ghost'
                size='sm'
                onClick={() => window.location.assign('/account/settings/')}
              >
                账户
              </Button>
              <Button variant='ghost' size='sm' onClick={() => void identity.client?.logout()}>
                退出
              </Button>
            </>
          )}
        </div>
      </header>

      <div className='flex min-h-0 flex-1'>
        <section className='flex min-w-0 flex-1 flex-col'>
          <div className='flex min-h-0 flex-1 flex-col xl:flex-row'>
            <div className='min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-8'>
              <div className='mx-auto flex max-w-3xl flex-col gap-5'>
                {chat.messages.length === 0 && (
                  <div className='py-16 text-center'>
                    <p className='font-medium text-[var(--text-primary)]'>今天想学什么？</p>
                    <p className='mt-2 text-[var(--text-muted)] text-sm'>
                      输入一个主题，LingxiGraph 会组织课程引入、讲义、检测和可视化产物。
                    </p>
                  </div>
                )}
                {chat.messages.map((message) =>
                  message.role === 'user' ? (
                    <div key={message.id} className='flex justify-end'>
                      <div className='max-w-[min(78%,42rem)] rounded-2xl bg-[var(--text-primary)] px-4 py-3 text-[var(--text-inverse)] text-sm leading-6'>
                        {message.content}
                      </div>
                    </div>
                  ) : (
                    <article key={message.id} className='max-w-3xl'>
                      <div className='mb-2 flex items-center gap-2 text-[var(--text-muted)] text-xs'>
                        <span className='size-1.5 rounded-full bg-[var(--brand-accent)]' />
                        灵犀学习助手
                        {chat.isReconnecting && <span>· 正在同步</span>}
                      </div>
                      <ThinkingAndTools blocks={message.contentBlocks ?? []} />
                      <p className='whitespace-pre-wrap text-[var(--text-body)] text-sm leading-7'>
                        {message.content}
                      </p>
                    </article>
                  )
                )}
                {chat.error && (
                  <div className='rounded-xl border border-[var(--text-error)]/30 bg-[var(--text-error)]/5 px-3 py-2 text-[var(--text-error)] text-xs'>
                    {chat.error}
                  </div>
                )}
              </div>
            </div>
            <aside className='hidden min-h-0 min-w-0 border-[var(--border)] border-l bg-[var(--surface-1)] p-3 xl:flex xl:w-[min(52%,760px)]'>
              {chat.task ? (
                <WorkflowsEditorLoop live runtime={{ task: chat.task, events: chat.events }} />
              ) : (
                <div className='flex min-h-0 flex-1 items-center justify-center text-[var(--text-muted)] text-xs'>
                  LingxiGraph 运行图将在执行开始后显示
                </div>
              )}
            </aside>
          </div>

          <div className='border-[var(--border)] border-t bg-[var(--surface-1)] px-4 py-3 sm:px-8'>
            <form onSubmit={submit} className='mx-auto flex max-w-3xl items-end gap-2'>
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    event.currentTarget.form?.requestSubmit()
                  }
                }}
                rows={2}
                placeholder='输入你想学习的主题…'
                className='min-h-11 flex-1 resize-none rounded-xl border border-[var(--border-1)] bg-[var(--surface-2)] px-3 py-2.5 text-[var(--text-body)] text-sm outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--text-primary)]'
              />
              {chat.isSending ? (
                <Button type='button' variant='outline' onClick={chat.stopGeneration}>
                  停止
                </Button>
              ) : (
                <Button type='submit' variant='primary' disabled={!draft.trim()}>
                  发送
                </Button>
              )}
            </form>
            <p className='mx-auto mt-2 max-w-3xl text-[var(--text-muted)] text-[10px]'>
              Shift + Enter 换行 · 思考过程只展示 LingxiGraph 生成的安全阶段摘要
            </p>
          </div>
        </section>
        <ArtifactPanel
          resource={activeResource}
          resources={chat.resources}
          onSelect={(resource) => setActiveResourceId(resource.id)}
        />
      </div>
    </main>
  )
}
