/** File extensions the Tables CSV import accepts. */
export const IMPORTABLE_EXTENSIONS = ['csv', 'tsv'] as const

/**
 * Keeps only the CSV/TSV files out of a picker result. Pure over the file list so the import
 * controller can be exercised without a mounted file input or resource list.
 */
export function pickCsvFiles(files: FileList | File[] | null | undefined): File[] {
  if (!files) return []
  return Array.from(files).filter((file) => {
    const extension = file.name.split('.').pop()?.toLowerCase()
    return (IMPORTABLE_EXTENSIONS as readonly string[]).includes(extension ?? '')
  })
}
