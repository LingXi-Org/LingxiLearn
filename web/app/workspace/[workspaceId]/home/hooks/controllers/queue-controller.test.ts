import {
  lingxiIdempotencyKey,
  pendingQueueKey,
  queueKeyFor,
  queueHead,
  queueKeysContaining,
  queueMigration,
} from './queue-controller'

describe('queue controller', () => {
  it('resolves pending queue identity and stable retry keys', () => {
    const pending = pendingQueueKey('lingxi')
    expect(queueKeyFor('lingxi')).toBe(pending)
    expect(queueKeyFor('lingxi', 'task-1')).toBe('task-1')
    expect(queueMigration('lingxi', 'task-1')).toEqual({ from: pending, to: 'task-1' })
    expect(lingxiIdempotencyKey('pending-1', 'r2')).toBe('lingxi-message:pending-1:r2')
  })

  it('selects only a dispatchable, non-edited head', () => {
    const queue = [{ id: 'first' }, { id: 'second' }]
    expect(queueHead(queue, null, null, 'idle')).toEqual(queue[0])
    expect(queueHead(queue, 'first', null, 'idle')).toBeNull()
    expect(queueHead(queue, null, 'active-send', 'idle')).toBeNull()
    expect(queueHead(queue, null, null, 'active')).toBeNull()
  })

  it('finds every persisted bucket containing an accepted command', () => {
    expect(
      queueKeysContaining({ pending: [{ id: 'a' }], resolved: [{ id: 'a' }], other: [] }, 'a')
    ).toEqual(['pending', 'resolved'])
  })
})
