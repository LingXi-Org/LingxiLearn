'use client'

import { useState } from 'react'
import {
  Button,
  Modal,
  ModalClose,
  ModalContent,
  ModalDescription,
  ModalTitle,
  ModalTrigger,
} from '@/components/ui-kit'
import { X } from '@/components/ui-kit/icons'
import { useLingxiIdentity } from '@/lib/lingxi/lingxi-identity-provider'

interface AuthModalProps {
  children: React.ReactNode
  defaultView?: 'login' | 'signup'
  source?: string
}

export function AuthModal({ children, defaultView = 'login' }: AuthModalProps) {
  const identity = useLingxiIdentity()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const startAuth = async () => {
    if (!identity.client) return
    setBusy(true)
    try {
      if (defaultView === 'signup') await identity.client.register()
      else await identity.client.login()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onOpenChange={setOpen}>
      <ModalTrigger asChild>{children}</ModalTrigger>
      <ModalContent size='sm' className='bg-[var(--bg)] text-[var(--text-primary)]'>
        <ModalTitle className='sr-only'>登录灵犀智学</ModalTitle>
        <ModalDescription className='sr-only'>使用 LingxiIdentity 登录灵犀智学</ModalDescription>
        <div className='relative px-6 py-8'>
          <ModalClose className='absolute top-5 right-5 rounded-sm opacity-70 transition-opacity hover:opacity-100'>
            <X className='size-5 text-[var(--text-muted)]' />
            <span className='sr-only'>关闭</span>
          </ModalClose>
          <div className='pr-8'>
            <p className='text-[var(--text-muted)] text-sm'>灵犀智学</p>
            <h2 className='mt-2 text-[var(--text-primary)] text-xl'>
              {defaultView === 'signup' ? '开始学习' : '欢迎回来'}
            </h2>
            <p className='mt-2 text-[var(--text-muted)] text-sm leading-6'>
              使用 LingxiIdentity 统一身份进入学习工作台。
            </p>
          </div>
          <Button
            className='mt-7 w-full'
            variant='primary'
            disabled={!identity.configured || !identity.client || busy}
            onClick={() => void startAuth()}
          >
            {busy
              ? '正在跳转…'
              : identity.configured
                ? defaultView === 'signup'
                  ? '使用 LingxiIdentity 注册'
                  : '使用 LingxiIdentity 登录'
                : '身份服务未配置'}
          </Button>
        </div>
      </ModalContent>
    </Modal>
  )
}
