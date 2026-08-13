'use client'

import Link from 'next/link'
import { Chip } from '@/components/ui-kit'
import { useSession } from '@/lib/auth/session-provider'
import { AuthHeader } from '../components/auth-shell'

export default function VerifyPage() {
  const session = useSession()
  return (
    <div className='space-y-6 text-center'>
      <AuthHeader
        title={session.authenticated ? '身份验证完成' : '验证你的账户'}
        description={session.authenticated ? '你的灵犀身份会话已生效' : '继续注册流程以完成邮箱验证'}
      />
      {session.authenticated ? (
        <Chip variant='primary' fullWidth className='h-9' onClick={() => window.location.assign('/workspace/lingxi/home/')}>
          进入工作台
        </Chip>
      ) : (
        <Link href='/signup' className='block'>
          <Chip variant='primary' fullWidth className='h-9'>继续验证</Chip>
        </Link>
      )}
    </div>
  )
}
