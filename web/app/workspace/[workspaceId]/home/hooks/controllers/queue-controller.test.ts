import {
  lingxiIdempotencyKey,
  pendingQueueKey,
  queueKeyFor,
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
})
