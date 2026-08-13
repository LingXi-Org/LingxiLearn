import type { Metadata } from 'next'
import { NotIntegrated } from '@/ee/not-integrated'

export const metadata: Metadata = { title: '重置密码' }

export default function ResetPasswordPage() {
  return <NotIntegrated title='重置密码' />
}
