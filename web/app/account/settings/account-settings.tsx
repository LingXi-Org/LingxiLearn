'use client'

import { useCallback, useEffect, useState } from 'react'
import { Button, ChipInput, Label } from '@/components/ui-kit'
import { identityApi, type IdentitySession } from '@/lib/auth/identity-api'
import { useSession } from '@/lib/auth/session-provider'

type Section = 'profile' | 'security' | 'sessions'

function Field({
  label,
  children,
  hint,
}: {
  label: string
  children: React.ReactNode
  hint?: string
}) {
  return (
    <div className='space-y-2'>
      <Label>{label}</Label>
      {children}
      {hint && <p className='text-[var(--text-muted)] text-xs'>{hint}</p>}
    </div>
  )
}

function SettingsCard({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <section className='rounded-xl border border-[var(--border)] bg-[var(--surface-1)]'>
      <div className='border-[var(--border)] border-b px-5 py-4'>
        <h2 className='font-medium text-[var(--text-primary)] text-sm'>{title}</h2>
        <p className='mt-1 text-[var(--text-muted)] text-xs'>{description}</p>
      </div>
      <div className='space-y-5 p-5'>{children}</div>
    </section>
  )
}

function Status({ value, error = false }: { value: string; error?: boolean }) {
  if (!value) return null
  return <p className={error ? 'text-[var(--text-error)] text-xs' : 'text-[var(--text-success)] text-xs'}>{value}</p>
}

export function AccountSettings() {
  const session = useSession()
  const user = session.data?.user
  const [section, setSection] = useState<Section>('profile')
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [avatar, setAvatar] = useState('')
  const [profileStatus, setProfileStatus] = useState('')
  const [profileError, setProfileError] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [securityStatus, setSecurityStatus] = useState('')
  const [securityError, setSecurityError] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [emailCode, setEmailCode] = useState('')
  const [passwordVerificationId, setPasswordVerificationId] = useState('')
  const [emailVerificationId, setEmailVerificationId] = useState('')
  const [sessions, setSessions] = useState<IdentitySession[]>([])
  const [sessionsStatus, setSessionsStatus] = useState('')
  const [deactivateText, setDeactivateText] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (user) {
      setName(user.name || '')
      setUsername('')
      setAvatar(user.image || '')
      setNewEmail(user.email || '')
    }
  }, [user])

  useEffect(() => {
    if (session.ready && !session.authenticated) {
      window.location.assign('/login?callbackUrl=/account/settings/')
    }
  }, [session.authenticated, session.ready])

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await identityApi.sessions())
      setSessionsStatus('')
    } catch (cause) {
      setSessionsStatus(cause instanceof Error ? cause.message : '无法读取设备会话')
    }
  }, [])

  useEffect(() => {
    if (section === 'sessions' && session.authenticated) void loadSessions()
  }, [loadSessions, section, session.authenticated])

  if (!session.ready || !user) {
    return <main className='flex min-h-screen items-center justify-center text-[var(--text-muted)] text-sm'>正在读取账户…</main>
  }

  const saveProfile = async () => {
    setBusy(true)
    setProfileStatus('')
    try {
      await identityApi.updateProfile({ name, username, avatar })
      await session.refresh()
      setProfileError(false)
      setProfileStatus('资料已保存')
    } catch (cause) {
      setProfileError(true)
      setProfileStatus(cause instanceof Error ? cause.message : '保存失败')
    } finally {
      setBusy(false)
    }
  }

  const verifyCurrentPassword = async () => {
    setBusy(true)
    try {
      const record = await identityApi.verifyPassword(currentPassword)
      setPasswordVerificationId(record.verificationRecordId)
      setSecurityError(false)
      setSecurityStatus('当前密码已验证，请在十分钟内完成修改')
    } catch (cause) {
      setSecurityError(true)
      setSecurityStatus(cause instanceof Error ? cause.message : '密码验证失败')
    } finally {
      setBusy(false)
    }
  }

  const changePassword = async () => {
    if (!passwordVerificationId) return
    setBusy(true)
    try {
      await identityApi.updatePassword(newPassword, passwordVerificationId)
      setCurrentPassword('')
      setNewPassword('')
      setPasswordVerificationId('')
      setSecurityError(false)
      setSecurityStatus('密码已更新')
    } catch (cause) {
      setSecurityError(true)
      setSecurityStatus(cause instanceof Error ? cause.message : '密码更新失败')
    } finally {
      setBusy(false)
    }
  }

  const sendEmailCode = async () => {
    if (!passwordVerificationId) return
    setBusy(true)
    try {
      const record = await identityApi.sendEmailVerification(newEmail)
      setEmailVerificationId(record.verificationRecordId)
      setSecurityError(false)
      setSecurityStatus('验证码已发送到新邮箱')
    } catch (cause) {
      setSecurityError(true)
      setSecurityStatus(cause instanceof Error ? cause.message : '验证码发送失败')
    } finally {
      setBusy(false)
    }
  }

  const changeEmail = async () => {
    if (!passwordVerificationId || !emailVerificationId) return
    setBusy(true)
    try {
      const verified = await identityApi.verifyEmailCode(newEmail, emailVerificationId, emailCode)
      await identityApi.updateEmail(newEmail, passwordVerificationId, verified.verificationRecordId)
      await session.refresh()
      setEmailCode('')
      setEmailVerificationId('')
      setPasswordVerificationId('')
      setSecurityError(false)
      setSecurityStatus('邮箱已更新')
    } catch (cause) {
      setSecurityError(true)
      setSecurityStatus(cause instanceof Error ? cause.message : '邮箱更新失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className='min-h-screen bg-[var(--bg)] text-[var(--text-body)]'>
      <header className='border-[var(--border)] border-b bg-[var(--surface-1)]'>
        <div className='mx-auto flex h-14 max-w-5xl items-center justify-between px-5'>
          <button type='button' onClick={() => window.location.assign('/workspace/lingxi/home/')} className='flex items-center gap-2'>
            <span className='flex size-7 items-center justify-center rounded-lg bg-[var(--text-primary)] font-semibold text-[var(--text-inverse)] text-xs'>灵</span>
            <span className='font-medium text-sm'>账户设置</span>
          </button>
          <Button variant='ghost' size='sm' onClick={() => void session.logout()}>退出登录</Button>
        </div>
      </header>
      <div className='mx-auto grid max-w-5xl gap-8 px-5 py-8 md:grid-cols-[180px_minmax(0,1fr)]'>
        <nav className='flex gap-1 md:flex-col'>
          {([
            ['profile', '个人资料'],
            ['security', '登录与安全'],
            ['sessions', '设备与账户'],
          ] as const).map(([value, label]) => (
            <button
              key={value}
              type='button'
              onClick={() => setSection(value)}
              className={`rounded-lg px-3 py-2 text-left text-sm ${section === value ? 'bg-[var(--surface-3)] text-[var(--text-primary)]' : 'text-[var(--text-muted)] hover:bg-[var(--surface-2)]'}`}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className='space-y-5'>
          {section === 'profile' && (
            <SettingsCard title='个人资料' description='这些信息会显示在灵犀智学的账户与协作界面中。'>
              <Field label='姓名'><ChipInput value={name} onChange={(event) => setName(event.target.value)} /></Field>
              <Field label='用户名'><ChipInput value={username} onChange={(event) => setUsername(event.target.value)} /></Field>
              <Field label='头像地址' hint='使用 HTTPS 图片地址。'><ChipInput value={avatar} onChange={(event) => setAvatar(event.target.value)} /></Field>
              <Status value={profileStatus} error={profileError} />
              <div><Button variant='primary' disabled={busy} onClick={() => void saveProfile()}>保存资料</Button></div>
            </SettingsCard>
          )}

          {section === 'security' && (
            <>
              <SettingsCard title='验证当前密码' description='修改邮箱或密码前需要一次短期身份验证。'>
                <Field label='当前密码'><ChipInput type='password' autoComplete='current-password' value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></Field>
                <div><Button variant='primary' disabled={busy || !currentPassword} onClick={() => void verifyCurrentPassword()}>验证密码</Button></div>
              </SettingsCard>
              <SettingsCard title='修改密码' description='使用至少八位且不易猜测的新密码。'>
                <Field label='新密码'><ChipInput type='password' autoComplete='new-password' value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></Field>
                <div><Button variant='primary' disabled={busy || !passwordVerificationId || newPassword.length < 8} onClick={() => void changePassword()}>更新密码</Button></div>
              </SettingsCard>
              <SettingsCard title='修改邮箱' description={`当前邮箱：${user.email || '未设置'}`}>
                <Field label='新邮箱'><ChipInput type='email' value={newEmail} onChange={(event) => setNewEmail(event.target.value)} /></Field>
                <div><Button disabled={busy || !passwordVerificationId || !newEmail} onClick={() => void sendEmailCode()}>发送验证码</Button></div>
                {emailVerificationId && <Field label='邮箱验证码'><ChipInput inputMode='numeric' value={emailCode} onChange={(event) => setEmailCode(event.target.value)} /></Field>}
                {emailVerificationId && <div><Button variant='primary' disabled={busy || emailCode.length < 4} onClick={() => void changeEmail()}>验证并更新邮箱</Button></div>}
                <Status value={securityStatus} error={securityError} />
              </SettingsCard>
            </>
          )}

          {section === 'sessions' && (
            <>
              <SettingsCard title='登录设备' description='查看并撤销你的 LingxiIdentity 设备会话。'>
                {sessions.length === 0 && <p className='text-[var(--text-muted)] text-sm'>暂无可显示的设备会话。</p>}
                {sessions.map((item) => (
                  <div key={item.id} className='flex items-center justify-between gap-4 rounded-lg border border-[var(--border)] px-3 py-3'>
                    <div className='min-w-0'>
                      <p className='truncate text-[var(--text-primary)] text-sm'>{item.applicationName || '灵犀应用'}{item.isCurrent ? ' · 当前设备' : ''}</p>
                      <p className='mt-1 text-[var(--text-muted)] text-xs'>{item.lastUsedAt ? `最近使用 ${new Date(item.lastUsedAt).toLocaleString()}` : '使用时间未知'}</p>
                    </div>
                    <Button variant='outline' size='sm' onClick={async () => { await identityApi.revokeSession(item.id); if (item.isCurrent) window.location.assign('/login'); else await loadSessions() }}>撤销</Button>
                  </div>
                ))}
                <Status value={sessionsStatus} error />
              </SettingsCard>
              <SettingsCard title='停用账户' description='停用后会立即撤销全部会话，需要管理员恢复才能再次登录。'>
                <Field label='输入“停用账户”以确认'><ChipInput value={deactivateText} onChange={(event) => setDeactivateText(event.target.value)} /></Field>
                <div><Button variant='destructive' disabled={busy || deactivateText !== '停用账户'} onClick={async () => { setBusy(true); try { await identityApi.deactivate(); window.location.assign('/') } finally { setBusy(false) } }}>停用账户</Button></div>
              </SettingsCard>
            </>
          )}
        </div>
      </div>
    </main>
  )
}
