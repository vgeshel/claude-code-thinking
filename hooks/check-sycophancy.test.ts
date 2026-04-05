import { describe, expect, it } from 'bun:test'
import { checkSycophancy } from './check-sycophancy'

describe('checkSycophancy', () => {
  it('returns null for normal messages', () => {
    expect(checkSycophancy('Here is the implementation.')).toBeNull()
  })

  it('detects "you are right"', () => {
    expect(checkSycophancy('You are right, let me fix that.')).not.toBeNull()
  })

  it('detects "good point"', () => {
    expect(checkSycophancy('Good point. I will update the code.')).not.toBeNull()
  })

  it('detects "that makes sense"', () => {
    expect(checkSycophancy('That makes sense. Updating now.')).not.toBeNull()
  })

  it('detects "great idea"', () => {
    expect(checkSycophancy('Great idea! Let me implement that.')).not.toBeNull()
  })

  it('detects "great question"', () => {
    expect(checkSycophancy('Great question! The answer is...')).not.toBeNull()
  })

  it('is case insensitive', () => {
    expect(checkSycophancy('YOU ARE RIGHT about this.')).not.toBeNull()
  })

  it('only checks first 300 chars', () => {
    const long = 'x'.repeat(301) + 'you are right'
    expect(checkSycophancy(long)).toBeNull()
  })
})
