'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Checkbox, Chip, ChipInput, ChipSelect } from '@/components/ui-kit'
import { Settings as SettingsIcon, Table as TableIcon } from '@/components/ui-kit/icons'
import {
  API_BASE,
  api,
  type KnowledgeBaseItem,
  type KnowledgeDocumentItem,
  type WorkspaceFileItem,
  type WorkspaceFolderItem,
  type WorkspaceTableItem,
} from '@/lib/lingxi/api'
import { userFacingError, workspaceCopy } from '@/lib/product-copy'
import { Resource } from '@/app/workspace/[workspaceId]/components'
import { SettingsField } from '@/app/workspace/[workspaceId]/settings/components/settings-field'
import { SettingsPanel } from '@/app/workspace/[workspaceId]/settings/components/settings-panel'

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
    <Resource>
      <Resource.Header icon={SettingsIcon} title={title} />
      <main className='min-h-0 flex-1 overflow-y-auto p-6'>
        <p className='mx-auto mb-5 max-w-[1100px] text-[12px] text-[var(--text-muted)]'>
          {description}
        </p>
        {children}
      </main>
    </Resource>
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
    <Chip type={type} disabled={disabled} onClick={onClick} className='text-[12px]'>
      {children}
    </Chip>
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
      .catch((e) => setError(userFacingError(e, 'loadFailed')))
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
      setError(userFacingError(e, 'uploadFailed'))
    }
  }
  const createText = async () => {
    try {
      await api.createWorkspaceFile('新建文档.md', '# 新文档\n', 'text/markdown', 'utf-8', folderId)
      reload()
    } catch (e) {
      setError(userFacingError(e, 'saveFailed'))
    }
  }
  const createFolder = async () => {
    if (!folderName.trim()) return
    try {
      await api.createWorkspaceFolder(folderName.trim(), folderId)
      setFolderName('')
      reload()
    } catch (e) {
      setError(userFacingError(e, 'saveFailed'))
    }
  }
  return (
    <Shell
      title={workspaceCopy.resources.files.title}
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
          <Empty>{archived ? '没有归档文件' : workspaceCopy.resources.files.empty}</Empty>
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

export function TablesPage() {
  const router = useRouter()
  const [tables, setTables] = useState<WorkspaceTableItem[]>([])
  const reload = useCallback(() => {
    void api
      .workspaceTables()
      .then((result) => setTables(result.tables))
      .catch(() => setTables([]))
  }, [])
  useEffect(() => {
    reload()
  }, [reload])
  return (
    <Resource>
      <Resource.Header icon={TableIcon} title='学习记录' />
      <div className='min-h-0 flex-1 overflow-y-auto p-4'>
        <Resource.Table
          columns={[
            { id: 'name', header: '表格' },
            { id: 'rows', header: '行数' },
            { id: 'columns', header: '列数' },
          ]}
          rows={tables.map((table) => ({
            id: table.id,
            cells: {
              name: { label: table.name },
              rows: { label: String(table.totalRows ?? table.rowCount ?? 0) },
              columns: { label: String((table.columns || table.schema?.columns || []).length) },
            },
          }))}
          onRowClick={(tableId) => router.push(`/workspace/lingxi/tables/${tableId}`)}
        />
      </div>
    </Resource>
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
      title={workspaceCopy.resources.knowledge.title}
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
          <Empty>{workspaceCopy.resources.knowledge.empty}</Empty>
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
        <Resource.Table
          columns={[
            { id: 'task', header: '任务' },
            { id: 'status', header: '状态' },
            { id: 'startedAt', header: '开始时间' },
          ]}
          rows={logs.map((log) => ({
            id: String(log.id),
            cells: {
              task: { label: String(log.id) },
              status: { label: String(log.status) },
              startedAt: { label: String(log.startedAt || '') },
            },
          }))}
        />
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
    <SettingsPanel
      title='常规设置'
      description='账户、学习偏好和个人工作区名称/外观。团队、凭据、API Keys、SSO 与工作流设置不开放。'
    >
      <div className='w-full py-2'>
        <form onSubmit={(event) => void save(event)} className='mx-auto max-w-[680px] space-y-6'>
          <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
            <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>个人工作区</h2>
            <div className='mt-4'>
              <SettingsField label='名称'>
                <ChipInput
                  value={workspaceName}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                  maxLength={160}
                  className='w-full'
                />
              </SettingsField>
            </div>
          </section>
          <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
            <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>学习偏好</h2>
            <div className='mt-4 grid gap-4 sm:grid-cols-2'>
              <SettingsField label='学习阶段'>
                <ChipSelect
                  fullWidth
                  value={level}
                  onChange={setLevel}
                  options={[
                    { value: 'undergraduate', label: '本科' },
                    { value: 'graduate', label: '研究生' },
                    { value: 'professional', label: '工程实践' },
                  ]}
                />
              </SettingsField>
              <SettingsField label='语言'>
                <ChipSelect
                  fullWidth
                  value={locale}
                  onChange={setLocale}
                  options={[
                    { value: 'zh-CN', label: '简体中文' },
                    { value: 'en-US', label: 'English' },
                  ]}
                />
              </SettingsField>
            </div>
          </section>
          <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
            <h2 className='text-[14px] font-medium text-[var(--text-primary)]'>应用偏好</h2>
            <div className='mt-4'>
              <SettingsField label='主题'>
                <ChipSelect
                  fullWidth
                  value={theme}
                  onChange={setTheme}
                  options={[
                    { value: 'system', label: '跟随系统' },
                    { value: 'light', label: '浅色' },
                    { value: 'dark', label: '深色' },
                  ]}
                />
              </SettingsField>
            </div>
            <div className='mt-4 space-y-3 text-[12px] text-[var(--text-secondary)]'>
              <div className='flex items-center gap-2'>
                <Checkbox
                  checked={telemetryEnabled}
                  onCheckedChange={(checked) => setTelemetryEnabled(checked === true)}
                />
                <span>允许匿名体验诊断</span>
              </div>
              <div className='flex items-center gap-2'>
                <Checkbox
                  checked={billingNotificationsEnabled}
                  onCheckedChange={(checked) => setBillingNotificationsEnabled(checked === true)}
                />
                <span>接收用量提醒</span>
              </div>
              <div className='flex items-center gap-2'>
                <Checkbox
                  checked={showActionBar}
                  onCheckedChange={(checked) => setShowActionBar(checked === true)}
                />
                <span>显示操作栏</span>
              </div>
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
            href='/workspace/lingxi/settings/users'
            className='rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-4 hover:bg-[var(--surface-hover)]'
          >
            <p className='text-[13px] text-[var(--text-primary)]'>用户管理</p>
            <p className='mt-1 text-[11px] text-[var(--text-muted)]'>
              个人账户中心；工作区保持个人私有
            </p>
          </Link>
        </div>
      </div>
    </SettingsPanel>
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
  const columns = table?.columns || table?.schema?.columns || []
  const columnLabels: Record<string, string> = {
    task_id: '学习任务',
    event_kind: '学习事件',
    agent: '执行智能体',
    sequence: '序号',
    recorded_at: '记录时间',
    knowledge_point: '知识点',
    learning_state: '学习状态',
    mastery: '掌握度',
    progress: '学习进度',
    score: '得分',
    question: '题目',
    answer: '作答',
    result: '结果',
    summary: '学习摘要',
  }
  const displayColumns = columns.filter((column: any) => columnLabels[String(column.key)])
  return (
    <Resource>
      <Resource.Header icon={TableIcon} title={table?.name || '学习记录'} />
      <div className='min-h-0 flex-1 overflow-y-auto p-4'>
        <p className='mx-auto mb-4 max-w-[1100px] text-[12px] text-[var(--text-muted)]'>
          学习记录为只读数据，不能手动新增或修改。
        </p>
        <Resource.Table
          columns={displayColumns.map((column: any) => ({
            id: String(column.id || column.key),
            header: columnLabels[String(column.key)],
          }))}
          rows={rows.map((row: any) => ({
            id: String(row.id),
            cells: Object.fromEntries(
              displayColumns.map((column: any) => {
                const id = String(column.id || column.key)
                return [id, { label: String((row.data || row.values)?.[column.key] ?? '') }]
              })
            ),
          }))}
        />
      </div>
    </Resource>
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
