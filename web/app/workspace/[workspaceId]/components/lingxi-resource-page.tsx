'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import {
  API_BASE,
  api,
  type KnowledgeBaseItem,
  type KnowledgeDocumentItem,
  type WorkspaceFileItem,
  type WorkspaceFolderItem,
  type WorkspaceTableItem,
} from '@/lib/lingxi/api'

type ResourceKind = 'files' | 'tables' | 'knowledge' | 'logs' | 'settings'

function Shell({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div className='flex h-full min-h-0 flex-col bg-[var(--bg)]'>
      <header className='flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4'>
        <div>
          <h1 className='text-[15px] font-medium text-[var(--text-primary)]'>{title}</h1>
          <p className='mt-1 text-[12px] text-[var(--text-muted)]'>{description}</p>
        </div>
      </header>
      <main className='min-h-0 flex-1 overflow-y-auto p-6'>{children}</main>
    </div>
  )
}

function ActionButton({
  children,
  onClick,
  type = 'button',
  disabled = false,
}: {
  children: React.ReactNode
  onClick?: () => void
  type?: 'button' | 'submit'
  disabled?: boolean
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className='rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-[12px] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] disabled:cursor-not-allowed disabled:opacity-50'
    >
      {children}
    </button>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className='rounded-[12px] border border-dashed border-[var(--border)] p-10 text-center text-[13px] text-[var(--text-muted)]'>
      {children}
    </div>
  )
}

function FilesPage() {
  const [files, setFiles] = useState<WorkspaceFileItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [archived, setArchived] = useState(false)
  const [folders, setFolders] = useState<WorkspaceFolderItem[]>([])
  const [folderId, setFolderId] = useState<string | null>(null)
  const [folderName, setFolderName] = useState('')
  const reload = useCallback(() => {
    setLoading(true)
    void Promise.all([
      api.workspaceFiles(archived ? 'archived' : 'active', folderId),
      api.workspaceFolders(archived ? 'archived' : 'active'),
    ])
      .then(([fileResult, folderResult]) => {
        setFiles(fileResult.files)
        setFolders(folderResult.folders)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [archived, folderId])
  useEffect(() => {
    reload()
  }, [reload])
  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 20 * 1024 * 1024) {
      setError('单个文件不能超过 20 MiB')
      return
    }
    const bytes = new Uint8Array(await file.arrayBuffer())
    let binary = ''
    for (let i = 0; i < bytes.length; i += 0x8000)
      binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
    try {
      await api.createWorkspaceFile(
        file.name,
        btoa(binary),
        file.type || 'application/octet-stream',
        'base64',
        folderId
      )
      reload()
    } catch (e) {
      setError(String(e))
    }
  }
  const createText = async () => {
    try {
      await api.createWorkspaceFile('新建文档.md', '# 新文档\n', 'text/markdown', 'utf-8', folderId)
      reload()
    } catch (e) {
      setError(String(e))
    }
  }
  const createFolder = async () => {
    if (!folderName.trim()) return
    try {
      await api.createWorkspaceFolder(folderName.trim(), folderId)
      setFolderName('')
      reload()
    } catch (e) {
      setError(String(e))
    }
  }
  return (
    <Shell
      title='Files'
      description='私有工作区文件；文本、Markdown、JSON、CSV 可编辑，二进制文件只读预览。'
    >
      <div className='mx-auto max-w-[960px]'>
        <div className='mb-4 flex flex-wrap items-center gap-2'>
          <label className='cursor-pointer rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-[12px] text-[var(--text-primary)]'>
            上传文件
            <input type='file' className='hidden' onChange={(event) => void upload(event)} />
          </label>
          <ActionButton onClick={() => void createText()}>新建文本</ActionButton>
          <ActionButton onClick={() => setArchived((value) => !value)}>
            {archived ? '查看当前文件' : '查看归档'}
          </ActionButton>
        </div>
        <div className='mb-4 flex flex-wrap items-center gap-2 rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-3'>
          <button
            type='button'
            className='text-[12px] text-[var(--text-secondary)] hover:underline'
            onClick={() => setFolderId(null)}
          >
            全部文件
          </button>
          {folders
            .filter((folder) => !folder.parentId)
            .map((folder) => (
              <button
                key={folder.id}
                type='button'
                className={`text-[12px] hover:underline ${folderId === folder.id ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'}`}
                onClick={() => setFolderId(folder.id)}
              >
                {folder.name}
              </button>
            ))}
          {!archived && (
            <form
              className='ml-auto flex gap-2'
              onSubmit={(event) => {
                event.preventDefault()
                void createFolder()
              }}
            >
              <input
                className='w-[150px] rounded-[6px] border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1 text-[11px] text-[var(--text-primary)]'
                value={folderName}
                onChange={(event) => setFolderName(event.target.value)}
                placeholder='新建文件夹'
              />
              <ActionButton type='submit'>创建</ActionButton>
            </form>
          )}
        </div>
        {error && <p className='mb-3 text-[12px] text-red-500'>{error}</p>}
        {loading ? (
          <p className='py-8 text-center text-[13px] text-[var(--text-muted)]'>正在加载…</p>
        ) : files.length === 0 ? (
          <Empty>{archived ? '没有归档文件' : '还没有文件'}</Empty>
        ) : (
          <div className='divide-y divide-[var(--border)] rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)]'>
            {files.map((file) => (
              <div key={file.id} className='flex items-center justify-between gap-3 px-4 py-3'>
                <div className='min-w-0'>
                  <Link
                    className='truncate text-[13px] text-[var(--text-primary)] hover:underline'
                    href={`/workspace/lingxi/files/${file.id}`}
                  >
                    {file.name}
                  </Link>
                  <p className='text-[11px] text-[var(--text-muted)]'>
                    {file.mimeType || file.type || 'unknown'} · {file.size} bytes
                  </p>
                </div>
                <div className='flex items-center gap-2'>
                  {file.url && (
                    <a
                      className='text-[11px] text-[var(--text-secondary)] hover:underline'
                      href={file.url}
                      target='_blank'
                      rel='noreferrer'
                    >
                      预览
                    </a>
                  )}
                  {!archived && (
                    <ActionButton
                      onClick={() => void api.archiveWorkspaceFile(file.id).then(reload)}
                    >
                      归档
                    </ActionButton>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  )
}

function TablesPage() {
  const [tables, setTables] = useState<WorkspaceTableItem[]>([])
  const [name, setName] = useState('')
  const reload = useCallback(() => {
    void api
      .workspaceTables()
      .then((result) => setTables(result.tables || result.data?.tables || []))
      .catch(() => setTables([]))
  }, [])
  useEffect(() => {
    reload()
  }, [reload])
  const create = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    await api.createWorkspaceTable(name.trim())
    setName('')
    reload()
  }
  return (
    <Shell
      title='Tables'
      description='七类原生列类型：string、number、currency、boolean、date、json、select。'
    >
      <div className='mx-auto max-w-[960px]'>
        <form className='mb-4 flex gap-2' onSubmit={(event) => void create(event)}>
          <input
            className='min-w-0 flex-1 rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[12px] text-[var(--text-primary)]'
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder='表格名称'
          />
          <ActionButton type='submit'>新建表格</ActionButton>
        </form>
        {tables.length === 0 ? (
          <Empty>还没有表格</Empty>
        ) : (
          <div className='grid gap-3 sm:grid-cols-2'>
            {tables.map((table) => (
              <Link
                key={table.id}
                href={`/workspace/lingxi/tables/${table.id}`}
                className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-4 hover:bg-[var(--surface-hover)]'
              >
                <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>{table.name}</h2>
                <p className='mt-1 text-[12px] text-[var(--text-muted)]'>
                  {table.totalRows ?? table.rowCount ?? 0} 行 ·{' '}
                  {(table.columns || table.schema?.columns || []).length} 列
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Shell>
  )
}

function KnowledgePage() {
  const [bases, setBases] = useState<KnowledgeBaseItem[]>([])
  const [name, setName] = useState('')
  const reload = useCallback(() => {
    void api
      .workspaceKnowledge()
      .then((result) => setBases(result.knowledgeBases || result.data || []))
      .catch(() => setBases([]))
  }, [])
  useEffect(() => {
    reload()
  }, [reload])
  const create = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    await api.createKnowledgeBase(name.trim())
    setName('')
    reload()
  }
  return (
    <Shell
      title='Knowledge'
      description='个人知识库、文档、分块、标签和中英文搜索；不启用外部连接器。'
    >
      <div className='mx-auto max-w-[960px]'>
        <form className='mb-4 flex gap-2' onSubmit={(event) => void create(event)}>
          <input
            className='min-w-0 flex-1 rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[12px] text-[var(--text-primary)]'
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder='知识库名称'
          />
          <ActionButton type='submit'>新建知识库</ActionButton>
        </form>
        {bases.length === 0 ? (
          <Empty>还没有知识库</Empty>
        ) : (
          <div className='grid gap-3 sm:grid-cols-2'>
            {bases.map((base) => (
              <Link
                key={base.id}
                href={`/workspace/lingxi/knowledge/${base.id}`}
                className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-4 hover:bg-[var(--surface-hover)]'
              >
                <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>{base.name}</h2>
                <p className='mt-1 text-[12px] text-[var(--text-muted)]'>
                  {base.documentCount ?? 0} 篇文档
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Shell>
  )
}

function LogsPage() {
  const [logs, setLogs] = useState<Array<Record<string, any>>>([])
  useEffect(() => {
    void api
      .logs()
      .then((result) => setLogs(result.data || []))
      .catch(() => setLogs([]))
  }, [])
  return (
    <Shell
      title='Logs'
      description='统一汇总 LingxiGraph 任务事件和资源活动；只读审计，不提供工作流重跑。'
    >
      <div className='mx-auto max-w-[1100px]'>
        <div className='mb-4 flex justify-end'>
          <a
            className='rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-[12px] text-[var(--text-primary)]'
            href={`${API_BASE}/api/logs/export?format=csv`}
          >
            导出 CSV
          </a>
        </div>
        {logs.length === 0 ? (
          <Empty>还没有任务日志</Empty>
        ) : (
          <div className='overflow-x-auto rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)]'>
            <table className='w-full text-left text-[12px]'>
              <thead>
                <tr className='border-b border-[var(--border)] text-[var(--text-muted)]'>
                  <th className='px-4 py-3'>任务</th>
                  <th className='px-4 py-3'>状态</th>
                  <th className='px-4 py-3'>开始时间</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={String(log.id)}
                    className='border-b border-[var(--border)] last:border-0'
                  >
                    <td className='px-4 py-3 text-[var(--text-primary)]'>{String(log.id)}</td>
                    <td className='px-4 py-3 text-[var(--text-secondary)]'>{String(log.status)}</td>
                    <td className='px-4 py-3 text-[var(--text-muted)]'>
                      {String(log.startedAt || '')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Shell>
  )
}

function SettingsPage() {
  const [workspaceName, setWorkspaceName] = useState('灵犀智学')
  const [level, setLevel] = useState('undergraduate')
  const [locale, setLocale] = useState('zh-CN')
  const [theme, setTheme] = useState('system')
  const [telemetryEnabled, setTelemetryEnabled] = useState(true)
  const [billingNotificationsEnabled, setBillingNotificationsEnabled] = useState(true)
  const [showActionBar, setShowActionBar] = useState(true)
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    void Promise.all([api.workspace(), api.preferences(), api.userSettings()])
      .then(([workspace, preference, settings]) => {
        setWorkspaceName(String(workspace.workspace?.name || '灵犀智学'))
        setLevel(String(preference.preferences?.level || 'undergraduate'))
        setLocale(String(preference.preferences?.locale || 'zh-CN'))
        setTheme(String(settings.data?.theme || 'system'))
        setTelemetryEnabled(settings.data?.telemetryEnabled !== false)
        setBillingNotificationsEnabled(settings.data?.billingUsageNotificationsEnabled !== false)
        setShowActionBar(settings.data?.showActionBar !== false)
      })
      .catch(() => undefined)
  }, [])
  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    await api.updateWorkspace({ name: workspaceName })
    await api.updatePreferences({ level, locale })
    await api.updateUserSettings({
      theme,
      telemetryEnabled,
      billingUsageNotificationsEnabled: billingNotificationsEnabled,
      showActionBar,
    })
    setSaved(true)
  }
  return (
    <Shell
      title='Settings'
      description='账户、学习偏好和个人工作区名称/外观。团队、凭据、API Keys、SSO 与工作流设置不开放。'
    >
      <form onSubmit={(event) => void save(event)} className='mx-auto max-w-[680px] space-y-6'>
        <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
          <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>个人工作区</h2>
          <label className='mt-4 block text-[12px] text-[var(--text-muted)]'>
            名称
            <input
              className='mt-2 w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-[13px] text-[var(--text-primary)]'
              value={workspaceName}
              onChange={(event) => setWorkspaceName(event.target.value)}
              maxLength={160}
            />
          </label>
        </section>
        <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
          <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>学习偏好</h2>
          <div className='mt-4 grid gap-4 sm:grid-cols-2'>
            <label className='text-[12px] text-[var(--text-muted)]'>
              学习阶段
              <select
                className='mt-2 w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-[13px] text-[var(--text-primary)]'
                value={level}
                onChange={(event) => setLevel(event.target.value)}
              >
                <option value='undergraduate'>本科</option>
                <option value='graduate'>研究生</option>
                <option value='professional'>工程实践</option>
              </select>
            </label>
            <label className='text-[12px] text-[var(--text-muted)]'>
              语言
              <select
                className='mt-2 w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-[13px] text-[var(--text-primary)]'
                value={locale}
                onChange={(event) => setLocale(event.target.value)}
              >
                <option value='zh-CN'>简体中文</option>
                <option value='en-US'>English</option>
              </select>
            </label>
          </div>
        </section>
        <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
          <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>应用偏好</h2>
          <label className='mt-4 block text-[12px] text-[var(--text-muted)]'>
            主题
            <select
              className='mt-2 w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-[13px] text-[var(--text-primary)]'
              value={theme}
              onChange={(event) => setTheme(event.target.value)}
            >
              <option value='system'>跟随系统</option>
              <option value='light'>浅色</option>
              <option value='dark'>深色</option>
            </select>
          </label>
          <div className='mt-4 space-y-3 text-[12px] text-[var(--text-secondary)]'>
            <label className='flex items-center gap-2'>
              <input
                type='checkbox'
                checked={telemetryEnabled}
                onChange={(event) => setTelemetryEnabled(event.target.checked)}
              />
              允许匿名体验诊断
            </label>
            <label className='flex items-center gap-2'>
              <input
                type='checkbox'
                checked={billingNotificationsEnabled}
                onChange={(event) => setBillingNotificationsEnabled(event.target.checked)}
              />
              接收用量提醒
            </label>
            <label className='flex items-center gap-2'>
              <input
                type='checkbox'
                checked={showActionBar}
                onChange={(event) => setShowActionBar(event.target.checked)}
              />
              显示操作栏
            </label>
          </div>
        </section>
        <div className='flex items-center gap-3'>
          <ActionButton type='submit'>保存设置</ActionButton>
          {saved && <span className='text-[12px] text-[var(--text-muted)]'>已保存</span>}
        </div>
      </form>
      <div className='mx-auto mt-6 grid max-w-[680px] gap-3 sm:grid-cols-2'>
        <Link
          href='/account/settings'
          className='rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-4 hover:bg-[var(--surface-hover)]'
        >
          <p className='text-[13px] text-[var(--text-primary)]'>账户与安全</p>
          <p className='mt-1 text-[11px] text-[var(--text-muted)]'>
            个人资料、密码、邮箱和设备会话
          </p>
        </Link>
        <Link
          href='/workspace/lingxi/settings/billing'
          className='rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-4 hover:bg-[var(--surface-hover)]'
        >
          <p className='text-[13px] text-[var(--text-primary)]'>计费与用量</p>
          <p className='mt-1 text-[11px] text-[var(--text-muted)]'>内部学习额度与只读审计</p>
        </Link>
        <Link
          href='/workspace/lingxi/settings/users'
          className='rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-4 hover:bg-[var(--surface-hover)]'
        >
          <p className='text-[13px] text-[var(--text-primary)]'>用户管理</p>
          <p className='mt-1 text-[11px] text-[var(--text-muted)]'>
            个人账户中心；成员协作保留占位
          </p>
        </Link>
        <Link
          href='/workspace/lingxi/settings/integrations'
          className='rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-4 hover:bg-[var(--surface-hover)]'
        >
          <p className='text-[13px] text-[var(--text-primary)]'>未启用设置</p>
          <p className='mt-1 text-[11px] text-[var(--text-muted)]'>SSO、API Keys、凭据等占位页面</p>
        </Link>
      </div>
    </Shell>
  )
}

export function LingxiResourcePage({ kind }: { kind: ResourceKind }) {
  if (kind === 'files') return <FilesPage />
  if (kind === 'tables') return <TablesPage />
  if (kind === 'knowledge') return <KnowledgePage />
  if (kind === 'logs') return <LogsPage />
  return <SettingsPage />
}

export function LingxiTableDetail({ tableId }: { tableId: string }) {
  const [table, setTable] = useState<WorkspaceTableItem | null>(null)
  const [rows, setRows] = useState<Array<Record<string, any>>>([])
  const [draft, setDraft] = useState('{}')
  const reload = useCallback(() => {
    void Promise.all([api.workspaceTable(tableId), api.workspaceTableRows(tableId)])
      .then(([tableResult, rowResult]) => {
        setTable(tableResult.data.table)
        setRows(rowResult.data.rows || [])
      })
      .catch(() => undefined)
  }, [tableId])
  useEffect(() => {
    reload()
  }, [reload])
  const add = async () => {
    try {
      const data = JSON.parse(draft)
      await api.createWorkspaceRows(tableId, [data])
      setDraft('{}')
      reload()
    } catch {
      /* keep invalid JSON visible */
    }
  }
  const columns = table?.columns || table?.schema?.columns || []
  return (
    <Shell title={table?.name || 'Table'} description='行列、视图、筛选和排序均为个人工作区资源。'>
      <div className='mx-auto max-w-[1100px]'>
        <div className='mb-4 flex gap-2'>
          <textarea
            className='min-h-[38px] flex-1 rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 font-mono text-[12px] text-[var(--text-primary)]'
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            aria-label='row JSON'
          />
          <ActionButton onClick={() => void add()}>添加行</ActionButton>
        </div>
        {rows.length === 0 ? (
          <Empty>还没有数据行</Empty>
        ) : (
          <div className='overflow-x-auto rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)]'>
            <table className='w-full text-left text-[12px]'>
              <thead>
                <tr className='border-b border-[var(--border)]'>
                  {columns.map((column: any) => (
                    <th
                      key={String(column.id || column.key)}
                      className='px-3 py-2 text-[var(--text-muted)]'
                    >
                      {String(column.name || column.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any) => (
                  <tr
                    key={String(row.id)}
                    className='border-b border-[var(--border)] last:border-0'
                  >
                    {columns.map((column: any) => (
                      <td
                        key={String(column.id || column.key)}
                        className='px-3 py-2 text-[var(--text-primary)]'
                      >
                        {String((row.data || row.values)?.[column.key] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Shell>
  )
}

export function LingxiKnowledgeDetail({ baseId }: { baseId: string }) {
  const [baseName, setBaseName] = useState('Knowledge')
  const [documents, setDocuments] = useState<KnowledgeDocumentItem[]>([])
  const [name, setName] = useState('')
  const [content, setContent] = useState('')
  const reload = useCallback(() => {
    void Promise.all([api.workspaceKnowledge(), api.knowledgeDocuments(baseId)])
      .then(([bases, docs]) => {
        setBaseName((bases.data || []).find((base) => base.id === baseId)?.name || 'Knowledge')
        setDocuments(docs.documents || docs.data || [])
      })
      .catch(() => undefined)
  }, [baseId])
  useEffect(() => {
    reload()
  }, [reload])
  const create = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    await api.createKnowledgeDocument(baseId, name.trim(), content, 'text/plain')
    setName('')
    setContent('')
    reload()
  }
  return (
    <Shell title={baseName} description='文档内容会切分为可检索块；外部连接器已隐藏。'>
      <div className='mx-auto max-w-[960px]'>
        <form
          onSubmit={(event) => void create(event)}
          className='mb-5 space-y-2 rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-4'
        >
          <input
            className='w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-[12px] text-[var(--text-primary)]'
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder='文档名称'
          />
          <textarea
            className='min-h-[100px] w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-[12px] text-[var(--text-primary)]'
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder='粘贴 TXT / Markdown / JSON / CSV 内容'
          />
          <ActionButton type='submit'>添加文档</ActionButton>
        </form>
        {documents.length === 0 ? (
          <Empty>还没有文档</Empty>
        ) : (
          <div className='divide-y divide-[var(--border)] rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)]'>
            {documents.map((doc) => (
              <Link
                key={doc.id}
                href={`/workspace/lingxi/knowledge/${baseId}/${doc.id}`}
                className='block px-4 py-3 hover:bg-[var(--surface-hover)]'
              >
                <p className='text-[13px] text-[var(--text-primary)]'>{doc.name}</p>
                <p className='text-[11px] text-[var(--text-muted)]'>
                  {doc.mimeType || 'text/plain'}
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Shell>
  )
}

export function LingxiDocumentDetail({
  baseId,
  documentId,
}: {
  baseId: string
  documentId: string
}) {
  const [document, setDocument] = useState<KnowledgeDocumentItem | null>(null)
  const [content, setContent] = useState('')
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    void api
      .knowledgeDocuments(baseId)
      .then((result) => {
        const row = (result.documents || result.data || []).find((item) => item.id === documentId)
        setDocument(row || null)
        setContent(row?.content || '')
      })
      .catch(() => undefined)
  }, [baseId, documentId])
  const save = async () => {
    await api.updateKnowledgeDocument(baseId, documentId, content)
    setSaved(true)
  }
  const documentEditable = Boolean(
    document &&
      !document.readOnly &&
      (document.mimeType?.startsWith('text/') ||
        /\.(md|markdown|json|csv|txt)$/i.test(document.name))
  )
  return (
    <Shell
      title={document?.name || 'Document'}
      description={
        documentEditable
          ? 'TXT、Markdown、JSON、CSV 可编辑；解析后的二进制文档只读。'
          : '该文档为只读知识资料。'
      }
    >
      <div className='mx-auto max-w-[960px]'>
        <textarea
          className='min-h-[420px] w-full rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-4 font-mono text-[13px] text-[var(--text-primary)]'
          value={content}
          onChange={(event) => {
            setContent(event.target.value)
            setSaved(false)
          }}
          readOnly={!documentEditable}
        />
        <div className='mt-3 flex items-center gap-3'>
          <ActionButton onClick={() => void save()} disabled={!documentEditable}>
            保存
          </ActionButton>
          {saved && <span className='text-[12px] text-[var(--text-muted)]'>已保存</span>}
        </div>
      </div>
    </Shell>
  )
}

export function LingxiFileDetail({ fileId }: { fileId: string }) {
  const [file, setFile] = useState<WorkspaceFileItem | null>(null)
  const [content, setContent] = useState('')
  const [encoding, setEncoding] = useState('utf-8')
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    let active = true
    void api
      .workspaceFile(fileId)
      .then(async (fileResult) => {
        if (!active) return
        setFile(fileResult.file)
        const isEditable = Boolean(
          fileResult.file &&
            (/^text\//.test(fileResult.file.mimeType || fileResult.file.type || '') ||
              /\.(md|markdown|json|csv|txt)$/i.test(fileResult.file.name))
        )
        if (!isEditable) return
        const contentResult = await api.workspaceFileContent(fileId)
        if (active) {
          setContent(contentResult.content)
          setEncoding(contentResult.encoding)
        }
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [fileId])
  const editable = Boolean(
    file &&
      !file.readOnly &&
      (/^text\//.test(file.mimeType || file.type || '') ||
        /\.(md|markdown|json|csv|txt)$/i.test(file.name))
  )
  const mime = file?.mimeType || file?.type || ''
  const previewUrl = file?.url ? `${API_BASE}${file.url}` : ''
  const isImage = mime.startsWith('image/')
  const isPdf = mime === 'application/pdf' || /\.pdf$/i.test(file?.name || '')
  const isHtml = mime === 'text/html' || /\.html?$/i.test(file?.name || '')
  return (
    <Shell
      title={file?.name || 'File'}
      description={
        editable ? '该文件可编辑，保存后写入个人工作区。' : '该文件为二进制格式，仅提供只读预览。'
      }
    >
      <div className='mx-auto max-w-[960px]'>
        {editable ? (
          <>
            <textarea
              className='min-h-[420px] w-full rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-4 font-mono text-[13px] text-[var(--text-primary)]'
              value={content}
              onChange={(event) => {
                setContent(event.target.value)
                setSaved(false)
              }}
              readOnly={encoding === 'base64'}
            />
            {encoding !== 'base64' && (
              <div className='mt-3 flex items-center gap-3'>
                <ActionButton
                  onClick={() =>
                    void api.updateWorkspaceFileContent(fileId, content).then(() => setSaved(true))
                  }
                >
                  保存
                </ActionButton>
                {saved && <span className='text-[12px] text-[var(--text-muted)]'>已保存</span>}
              </div>
            )}
          </>
        ) : (
          <div className='space-y-4 rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-4'>
            {previewUrl && isImage && (
              <img
                src={previewUrl}
                alt={file?.name || '预览'}
                className='max-h-[620px] max-w-full object-contain'
              />
            )}
            {previewUrl && isPdf && (
              <iframe
                src={previewUrl}
                title={file?.name || 'PDF 预览'}
                className='h-[620px] w-full rounded-[8px] border-0'
              />
            )}
            {previewUrl && isHtml && (
              <iframe
                src={previewUrl}
                title={file?.name || 'HTML 预览'}
                sandbox=''
                className='h-[620px] w-full rounded-[8px] border border-[var(--border)]'
              />
            )}
            {!isImage && !isPdf && !isHtml && (
              <p className='text-[13px] text-[var(--text-muted)]'>该格式支持只读下载或系统预览。</p>
            )}
            {previewUrl && (
              <a
                href={previewUrl}
                target='_blank'
                rel='noreferrer'
                className='text-[12px] text-[var(--text-secondary)] hover:underline'
              >
                打开只读预览
              </a>
            )}
          </div>
        )}
      </div>
    </Shell>
  )
}
