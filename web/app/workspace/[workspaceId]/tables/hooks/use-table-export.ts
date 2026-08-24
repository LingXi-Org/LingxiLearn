'use client'

import { useCallback } from 'react'
import { toast } from '@/components/ui-kit'
import { createLogger } from '@/lib/logger'
import { userFacingError } from '@/lib/product-copy'
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
        if (status === 'processing') toast.success('已开始导出')
      } catch (err) {
        logger.error('Failed to export table:', err)
        toast.error(userFacingError(err, 'loadFailed'))
      }
    },
    [workspaceId]
  )
}
