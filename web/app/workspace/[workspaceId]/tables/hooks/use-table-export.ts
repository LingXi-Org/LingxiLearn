'use client'

import { useCallback } from 'react'
import { toast } from '@sim/emcn'
import { createLogger } from '@/lib/logger'
import { exportTable } from '@/hooks/queries/tables'

const logger = createLogger('TablesCsvExport')

/**
 * CSV export action for a table row. Kept apart from the list controller and the import
 * controller so the export path can be exercised without either of them mounted.
 */
export function useExportTable(workspaceId: string): (tableId: string) => Promise<void> {
  return useCallback(
    async (tableId: string) => {
      try {
        const status = await exportTable(workspaceId, tableId)
        if (status === 'processing') toast.success('Export started')
      } catch (err) {
        logger.error('Failed to export table:', err)
        toast.error('Failed to export table')
      }
    },
    [workspaceId]
  )
}
