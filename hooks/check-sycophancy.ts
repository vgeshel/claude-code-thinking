#!/usr/bin/env bun

/**
 * Stop hook: blocks responses that begin with sycophantic agreement phrases.
 *
 * Sycophancy is a canary for shallow thinking. When Claude reflexively agrees
 * ("you're right", "good point", "great idea"), it usually means it hasn't
 * evaluated the user's input deeply enough. This hook forces a re-examination.
 */

const SYCOPHANCY_PATTERNS = [
  /you.re right/i,
  /you are right/i,
  /good point/i,
  /great idea/i,
  /that makes sense/i,
  /good catch/i,
  /excellent suggestion/i,
  /absolutely right/i,
  /that.s a great/i,
  /great question/i,
  /good question/i,
] as const

export function checkSycophancy(message: string): string | null {
  const snippet = message.slice(0, 300)
  for (const pattern of SYCOPHANCY_PATTERNS) {
    if (pattern.test(snippet)) {
      return `Sycophancy detected: "${snippet.slice(0, 80)}..." — rephrase without agreement phrases and re-examine whether your reasoning holds up.`
    }
  }
  return null
}

interface HookInput {
  stop_hook_active?: boolean
  last_assistant_message?: string
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
  const result = checkSycophancy(message)
  if (result) {
    console.error(result)
    process.exit(2)
  }
  process.exit(0)
}
