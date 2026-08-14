import type { Client } from 'ssh2'

export interface SSHConnectionConfig {
  host: string
  port?: number
  username: string
  password?: string | null
  privateKey?: string | null
  passphrase?: string | null
}

export function sanitizePath(value: string): string {
  const normalized = value.replaceAll('\\', '/').replace(/^\.\//, '')
  if (normalized.split('/').includes('..')) throw new Error('Path traversal is not allowed')
  return normalized
}

export function escapeShellArg(value: string): string {
  return value.replaceAll("'", "'\\''")
}

export function sanitizeCommand(value: string): string {
  return value.replace(/[\u0000\r\n]/g, ' ')
}

export async function createSSHConnection(_config: SSHConnectionConfig): Promise<Client> {
  throw new Error('SSH tools are not available in the Lingxi workspace')
}

export async function executeSSHCommand(_client: Client, _command: string): Promise<{
  stdout: string
  stderr: string
  exitCode: number
}> {
  throw new Error('SSH tools are not available in the Lingxi workspace')
}
