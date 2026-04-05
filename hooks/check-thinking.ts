#!/usr/bin/env bun

/**
 * Stop hook: blocks responses that lack the _I THOUGHT_ marker.
 *
 * The marker proves Claude worked through the 5-question deliberation
 * checklist before producing output. Without it, the response was likely
 * generated on autopilot. Short responses (< 40 chars) are exempt — not
 * every "Done." needs a full deliberation cycle.
 *
 * The hook checks both the last assistant message and the full transcript
 * (if available) because the marker may appear in an earlier text block
 * of the same turn, before tool calls.
 */

import { readFileSync } from 'node:fs'

const MARKER = '_I THOUGHT_'
const MIN_LENGTH = 40

export function checkThinking(message: string): string | null {
  if (message.length < MIN_LENGTH) return null
  if (message.includes(MARKER)) return null
  return 'Response missing _I THOUGHT_ proof of checklist. Work through the 5 questions before responding.'
}

export function checkTranscriptForMarker(transcriptPath: string): boolean {
  let lines: readonly string[]
  try {
    lines = readFileSync(transcriptPath, 'utf-8').trim().split('\n')
  } catch {
    return false
  }

  const assistantTexts: string[] = []
  for (let i = lines.length - 1; i >= 0; i--) {
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(lines[i]) as Record<string, unknown>
    } catch {
      continue
    }

    const entryType = typeof parsed.type === 'string' ? parsed.type : ''
    const message = parsed.message as
      | { content?: unknown[] }
      | undefined

    // Stop at real user messages, but skip tool_result entries (they're
    // interleaved in the same turn between assistant tool_use and response)
    if (entryType === 'user') {
      const content = message?.content ?? []
      const isToolResult = content.some(
        (block) =>
          typeof block === 'object' &&
          block !== null &&
          'type' in block &&
          (block as Record<string, unknown>).type === 'tool_result',
      )
      if (!isToolResult) break
      continue
    }

    if (entryType === 'assistant' && message?.content) {
      for (const block of message.content) {
        if (
          typeof block === 'object' &&
          block !== null &&
          'type' in block &&
          (block as Record<string, unknown>).type === 'text' &&
          'text' in block &&
          typeof (block as Record<string, unknown>).text === 'string'
        ) {
          assistantTexts.push((block as Record<string, unknown>).text as string)
        }
      }
    }
  }

  return assistantTexts.join('\n').includes(MARKER)
}

interface HookInput {
  stop_hook_active?: boolean
  last_assistant_message?: string
  transcript_path?: string
}

if (import.meta.main) {
  const raw = await Bun.stdin.text()
  let parsed: HookInput
  try {
    parsed = JSON.parse(raw) as HookInput
  } catch {
    process.exit(0)
  }
  if (parsed.stop_hook_active) process.exit(0)

  const message = parsed.last_assistant_message ?? ''
  if (message.length < MIN_LENGTH) process.exit(0)

  if (parsed.transcript_path) {
    if (checkTranscriptForMarker(parsed.transcript_path)) {
      process.exit(0)
    }
  }

  if (message.includes(MARKER)) {
    process.exit(0)
  }

  console.error(
    'Response missing _I THOUGHT_ proof of checklist. Work through the 5 questions before responding.',
  )
  process.exit(2)
}
