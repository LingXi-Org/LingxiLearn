/** Sort directions shared by transport contracts and client controls. */
export const LIST_SORT_ORDERS = ['asc', 'desc'] as const
export type ListSortOrder = (typeof LIST_SORT_ORDERS)[number]
