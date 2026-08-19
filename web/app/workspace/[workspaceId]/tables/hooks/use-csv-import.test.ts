/**
 * @vitest-environment node
 *
 * The CSV import controller runs against mocked React hooks, query mutations and the tray
 * store — it never mounts the resource list, which is exactly what the split guarantees.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mutateAsync, tray, toastSuccess, toastError } = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  tray: {
    startUpload: vi.fn(),
    setUploadPercent: vi.fn(),
    endUpload: vi.fn(),
    consumeCanceled: vi.fn(),
  },
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('react', () => ({
  useCallback: (fn: unknown) => fn,
  useRef: (init: unknown) => ({ current: init }),
  useState: (init: unknown) => [init, vi.fn()],
}))

vi.mock('@sim/emcn', () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}))

vi.mock('@sim/logger', () => ({
  createLogger: () => ({ debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() }),
}))

vi.mock('@/hooks/queries/tables', () => ({
  useImportCsv: () => ({ mutateAsync }),
}))

vi.mock('@/stores/table/import-tray/store', () => ({
  useImportTrayStore: { getState: () => tray },
}))

import { useCsvImport } from '@/app/workspace/[workspaceId]/tables/hooks/use-csv-import'

const WORKSPACE_ID = 'ws-1'

function makeController() {
  const getFolderPath = vi.fn(() => '/Reports')
  const controller = useCsvImport({ workspaceId: WORKSPACE_ID, getFolderPath })
  return { controller, getFolderPath }
}

function csvFile(name: string): File {
  return new File(['a,b\n1,2'], name)
}

beforeEach(() => {
  vi.clearAllMocks()
  mutateAsync.mockResolvedValue({})
})

describe('useCsvImport', () => {
  it('starts in the idle state with the static action label', () => {
    const { controller } = makeController()
    expect(controller.uploading).toBe(false)
    expect(controller.uploadProgress).toEqual({ completed: 0, total: 0 })
    expect(controller.uploadButtonLabel).toBe('Import CSV')
  })

  it('does nothing for an empty file list', async () => {
    const { controller, getFolderPath } = makeController()
    await controller.importFiles([])
    expect(mutateAsync).not.toHaveBeenCalled()
    expect(getFolderPath).not.toHaveBeenCalled()
  })

  it('imports files sequentially into the folder resolved at call time', async () => {
    mutateAsync.mockImplementation(async ({ onCreated, onProgress }) => {
      onCreated('imp-1')
      onProgress(50)
      return { tableId: 't1', importId: 'imp-1' }
    })
    const { controller, getFolderPath } = makeController()

    await controller.importFiles([csvFile('a.csv'), csvFile('b.tsv')])

    expect(mutateAsync).toHaveBeenCalledTimes(2)
    expect(getFolderPath).toHaveBeenCalledTimes(2)
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({
      workspaceId: WORKSPACE_ID,
      folderPath: '/Reports',
      file: expect.objectContaining({ name: 'a.csv' }),
    })
    expect(mutateAsync.mock.calls[1][0].file.name).toBe('b.tsv')
    expect(toastSuccess).toHaveBeenCalledTimes(2)
  })

  it('drives the tray upload lifecycle around each import', async () => {
    mutateAsync.mockImplementation(async ({ onCreated, onProgress }) => {
      onCreated('imp-1')
      onProgress(42)
      return {}
    })
    const { controller } = makeController()

    await controller.importFiles([csvFile('a.csv')])

    expect(tray.startUpload).toHaveBeenCalledWith({
      uploadId: 'imp-1',
      workspaceId: WORKSPACE_ID,
      title: 'a.csv',
    })
    expect(tray.setUploadPercent).toHaveBeenCalledWith('imp-1', 42)
    expect(tray.endUpload).toHaveBeenCalledWith('imp-1')
    expect(tray.consumeCanceled).toHaveBeenCalledWith('imp-1')
  })

  it('ends a failed tray upload and still imports the remaining files', async () => {
    let call = 0
    mutateAsync.mockImplementation(async ({ onCreated }) => {
      call += 1
      if (call === 1) {
        onCreated('imp-1')
        throw new Error('upload failed')
      }
      return {}
    })
    const { controller } = makeController()

    await controller.importFiles([csvFile('bad.csv'), csvFile('good.csv')])

    expect(mutateAsync).toHaveBeenCalledTimes(2)
    expect(tray.endUpload).toHaveBeenCalledWith('imp-1')
    // The failing file never reported completion, so no stale tray card is consumed.
    expect(tray.consumeCanceled).not.toHaveBeenCalled()
  })

  it('rejects a picker result without importable files', async () => {
    const { controller } = makeController()
    const event = { target: { files: [new File([''], 'notes.txt')] } }

    await controller.handleCsvChange(event as never)

    expect(toastError).toHaveBeenCalledWith('No CSV or TSV files selected')
    expect(mutateAsync).not.toHaveBeenCalled()
  })

  it('ignores an emptied picker selection silently', async () => {
    const { controller } = makeController()
    const event = { target: { files: [] } }

    await controller.handleCsvChange(event as never)

    expect(toastError).not.toHaveBeenCalled()
    expect(mutateAsync).not.toHaveBeenCalled()
  })

  it('imports the importable files out of a mixed picker result', async () => {
    const { controller } = makeController()
    const event = { target: { files: [new File([''], 'notes.txt'), csvFile('data.csv')] } }

    await controller.handleCsvChange(event as never)

    expect(mutateAsync).toHaveBeenCalledTimes(1)
    expect(mutateAsync.mock.calls[0][0].file.name).toBe('data.csv')
  })
})
