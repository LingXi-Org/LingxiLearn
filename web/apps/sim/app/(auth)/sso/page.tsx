import type { Metadata } from 'next'
import { NotIntegrated } from '@/ee/not-integrated'

export const metadata: Metadata = { title: '单点登录' }

export default function SSOPage() {
  return <NotIntegrated title='企业单点登录' />
}
