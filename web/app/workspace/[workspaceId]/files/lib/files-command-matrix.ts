/**
 * The single source of truth for which Files commands are available to the current user.
 *
 * Permissions decide command AVAILABILITY here, once — header actions, context menus, the
 * action bar, drag and drop, and keyboard shortcuts all read this matrix instead of
 * re-checking `canEdit` at every call site. A command missing from the matrix is a bug in the
 * matrix, not in twenty render functions.
 */
export interface FilesCommandAvailability {
  /** Open a folder or file — reading is never gated. */
  open: boolean
  /** Download a file or a selection archive — reading is never gated. */
  download: boolean
  /** Pin/unpin a row — a personal view preference, not an edit. */
  togglePin: boolean
  upload: boolean
  createFile: boolean
  createFolder: boolean
  rename: boolean
  move: boolean
  delete: boolean
  share: boolean
}

/** Derives the whole matrix from the workspace permission bit, in one place. */
export function getFilesCommandAvailability(canEdit: boolean): FilesCommandAvailability {
  return {
    open: true,
    download: true,
    togglePin: true,
    upload: canEdit,
    createFile: canEdit,
    createFolder: canEdit,
    rename: canEdit,
    move: canEdit,
    delete: canEdit,
    share: canEdit,
  }
}
