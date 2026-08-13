import type { Metadata } from 'next'
import { NotIntegrated } from '@/ee/not-integrated'

export const metadata: Metadata = { title: '注册' }

export default function SignupPage() {
  return <NotIntegrated title='注册账号' />
}
