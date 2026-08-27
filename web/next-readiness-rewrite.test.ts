/**
 * @vitest-environment node
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { once } from 'node:events'
import { copyFile, mkdir, mkdtemp, rm, symlink, writeFile } from 'node:fs/promises'
import { createServer, get as httpGet, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

function originOf(server: Server): string {
  const address = server.address() as AddressInfo
  return `http://127.0.0.1:${address.port}`
}

async function listen(server: Server): Promise<void> {
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
}

async function close(server: Server | undefined): Promise<void> {
  if (!server?.listening) return
  server.close()
  await once(server, 'close')
}

async function availablePort(): Promise<number> {
  const server = createServer()
  await listen(server)
  const port = (server.address() as AddressInfo).port
  await close(server)
  return port
}

async function stop(process: ChildProcess | undefined): Promise<void> {
  if (!process || process.exitCode !== null) return
  process.kill('SIGTERM')
  await once(process, 'exit')
}

async function request(url: string): Promise<{ body: string; status: number }> {
  return await new Promise((resolve, reject) => {
    const outgoing = httpGet(
      url,
      { headers: { 'user-agent': 'lingxilearn-readiness-test' } },
      (response) => {
        const chunks: Buffer[] = []
        response.on('data', (chunk) => chunks.push(Buffer.from(chunk)))
        response.on('end', () => {
          resolve({
            body: Buffer.concat(chunks).toString('utf-8'),
            status: response.statusCode ?? 0,
          })
        })
      }
    )
    outgoing.on('error', reject)
  })
}

describe('Next readiness rewrite boundary', () => {
  let apiStatus = 200
  let apiServer: Server | undefined
  let webProcess: ChildProcess | undefined
  let webOrigin: string
  let webLogs = ''
  let projectDir: string | undefined

  beforeAll(async () => {
    apiServer = createServer((request, response) => {
      if (request.url === '/ready') {
        response.writeHead(apiStatus, { 'content-type': 'application/json' })
        response.end(JSON.stringify({ status: apiStatus === 200 ? 'ready' : 'not_ready' }))
        return
      }
      response.writeHead(404)
      response.end()
    })
    await listen(apiServer)

    const webRoot = process.cwd()
    projectDir = await mkdtemp(join(tmpdir(), 'lingxilearn-next-readiness-'))
    await copyFile(join(webRoot, 'next.config.ts'), join(projectDir, 'next.config.ts'))
    await symlink(join(webRoot, 'node_modules'), join(projectDir, 'node_modules'), 'dir')
    await mkdir(join(projectDir, 'app'))
    await writeFile(
      join(projectDir, 'app', 'layout.tsx'),
      'export default function Layout({ children }: { children: React.ReactNode }) { return <html><body>{children}</body></html> }\n'
    )
    await writeFile(
      join(projectDir, 'app', 'page.tsx'),
      'export default function Page() { return null }\n'
    )

    const webPort = await availablePort()
    webOrigin = `http://127.0.0.1:${webPort}`
    webProcess = spawn(
      process.execPath,
      [
        join(webRoot, 'node_modules/next/dist/bin/next'),
        'dev',
        '--webpack',
        '--hostname',
        '127.0.0.1',
        '--port',
        String(webPort),
      ],
      {
        cwd: projectDir,
        env: {
          ...process.env,
          LINGXILEARN_API_ORIGIN: originOf(apiServer),
          NEXT_TELEMETRY_DISABLED: '1',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      }
    )
    webProcess.stdout?.on('data', (chunk) => {
      webLogs += chunk.toString()
    })
    webProcess.stderr?.on('data', (chunk) => {
      webLogs += chunk.toString()
    })

    const deadline = Date.now() + 45_000
    while (Date.now() < deadline) {
      if (webProcess.exitCode !== null) {
        throw new Error(`Next exited before becoming ready:\n${webLogs}`)
      }
      try {
        const response = await request(`${webOrigin}/ready`)
        if (response.status === 200) return
      } catch {
        // Next is still compiling or has not bound its port yet.
      }
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
    throw new Error(`Next did not expose the readiness rewrite:\n${webLogs}`)
  }, 60_000)

  afterAll(async () => {
    await stop(webProcess)
    await close(apiServer)
    if (projectDir) await rm(projectDir, { force: true, recursive: true })
  })

  it('returns 200 through Web when the API is ready', async () => {
    apiStatus = 200
    const response = await request(`${webOrigin}/ready`)
    expect(response.status).toBe(200)
    expect(JSON.parse(response.body)).toEqual({ status: 'ready' })
  })

  it('preserves the API not-ready status through Web', async () => {
    apiStatus = 503
    const response = await request(`${webOrigin}/ready`)
    expect(response.status).toBe(503)
    expect(JSON.parse(response.body)).toEqual({ status: 'not_ready' })
  })

  it('returns non-2xx through Web when the API is unavailable', async () => {
    await close(apiServer)
    const response = await request(`${webOrigin}/ready`)
    expect(response.status).toBeGreaterThanOrEqual(400)
  })
})
