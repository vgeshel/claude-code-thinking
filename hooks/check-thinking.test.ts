import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { describe, expect, it } from 'bun:test'
import { checkThinking, checkTranscriptForMarker } from './check-thinking'

describe('checkThinking', () => {
  it('returns null for short messages', () => {
    expect(checkThinking('Done.')).toBeNull()
  })

  it('returns null when marker is present', () => {
    const msg =
      '_I THOUGHT_\n\nHere is a detailed response that is long enough to be checked by the hook.'
    expect(checkThinking(msg)).toBeNull()
  })

  it('returns error when marker is absent from long message', () => {
    const msg =
      'Here is a detailed response that is long enough to be checked by the hook but has no marker.'
    expect(checkThinking(msg)).toContain('_I THOUGHT_')
  })

  it('returns null for exactly 39 chars', () => {
    expect(checkThinking('a'.repeat(39))).toBeNull()
  })

  it('returns error for 40+ chars without marker', () => {
    expect(checkThinking('a'.repeat(40))).not.toBeNull()
  })
})

describe('checkTranscriptForMarker', () => {
  function writeFakeTranscript(lines: readonly object[]): string {
    const tmpDir = mkdtempSync(path.join(os.tmpdir(), 'hook-test-'))
    const filePath = path.join(tmpDir, 'transcript.jsonl')
    writeFileSync(filePath, lines.map((l) => JSON.stringify(l)).join('\n'))
    return filePath
  }

  function cleanup(filePath: string) {
    rmSync(path.dirname(filePath), { recursive: true })
  }

  it('returns true when marker in current assistant turn', () => {
    const p = writeFakeTranscript([
      {
        type: 'user',
        message: { role: 'user', content: [{ type: 'text', text: 'hello' }] },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [{ type: 'text', text: '_I THOUGHT_\n\nResponse.' }],
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [{ type: 'tool_use', id: '1', name: 'Read' }],
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [{ type: 'text', text: 'Final text without marker.' }],
        },
      },
    ])
    expect(checkTranscriptForMarker(p)).toBe(true)
    cleanup(p)
  })

  it('returns false when no marker in current turn', () => {
    const p = writeFakeTranscript([
      {
        type: 'user',
        message: { role: 'user', content: [{ type: 'text', text: 'hello' }] },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [{ type: 'text', text: 'No marker here.' }],
        },
      },
    ])
    expect(checkTranscriptForMarker(p)).toBe(false)
    cleanup(p)
  })

  it('ignores marker from previous turn', () => {
    const p = writeFakeTranscript([
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [{ type: 'text', text: '_I THOUGHT_\n\nOld.' }],
        },
      },
      {
        type: 'user',
        message: {
          role: 'user',
          content: [{ type: 'text', text: 'new question' }],
        },
      },
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [{ type: 'text', text: 'No marker in new turn.' }],
        },
      },
    ])
    expect(checkTranscriptForMarker(p)).toBe(false)
    cleanup(p)
  })

  it('skips tool_result user entries within the same turn', () => {
    const p = writeFakeTranscript([
      {
        type: 'user',
        message: { content: [{ type: 'text', text: 'do something' }] },
      },
      {
        type: 'assistant',
        message: { content: [{ type: 'text', text: '_I THOUGHT_\n\nPlan.' }] },
      },
      {
        type: 'assistant',
        message: { content: [{ type: 'tool_use', id: '1', name: 'Bash' }] },
      },
      {
        type: 'user',
        message: { content: [{ type: 'tool_result', tool_use_id: '1' }] },
      },
      {
        type: 'assistant',
        message: {
          content: [{ type: 'text', text: 'Results without marker.' }],
        },
      },
    ])
    expect(checkTranscriptForMarker(p)).toBe(true)
    cleanup(p)
  })

  it('returns false for nonexistent file', () => {
    expect(checkTranscriptForMarker('/tmp/nonexistent-transcript.jsonl')).toBe(
      false,
    )
  })
})
