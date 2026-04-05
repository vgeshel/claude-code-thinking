# claude-thinking

A Claude Code plugin that enforces deliberate thinking, eliminates sycophancy, and improves response quality.

## What it does

When enabled, this plugin changes how Claude Code works:

1. **Deliberation checklist** — Before every substantive response, Claude works through 5 questions: What is being asked? What does a complete solution require? What do I not know? Does this conflict with anything? How will I verify this works?

2. **Zero sycophancy** — Blocks reflexive agreement phrases ("you're right", "good point", "great idea"). These are a canary for shallow thinking — if Claude is agreeing without examining, it hasn't evaluated deeply enough.

3. **Behavioral rules** — Think before acting, verify your own work, fix all problems (no "low priority" excuses), answer questions before jumping to action, finish everything the user asked for.

## How it works

The plugin has two parts:

- **Default agent** (`agents/thinking.md`) — Applies the thinking rules as a system prompt to every conversation. This is always active when the plugin is enabled.
- **Stop hooks** (`hooks/`) — Mechanically block responses that contain sycophantic phrases or lack the `_I THOUGHT_` deliberation marker. These catch violations that slip through the system prompt.

## Install

```bash
claude plugins:add /path/to/claude-thinking
```

Or if published to the marketplace:

```bash
claude plugins:add claude-thinking
```

## Requires

- [Bun](https://bun.sh) — the hooks are TypeScript scripts executed by Bun

## Run tests

```bash
cd hooks && bun test
```

## Customization

### Disable the thinking marker

If the `_I THOUGHT_` marker is too noisy for your workflow, remove the `check-thinking.ts` hook from `hooks/hooks.json`. The behavioral rules from the agent will still apply.

### Add sycophancy patterns

Edit the `SYCOPHANCY_PATTERNS` array in `hooks/check-sycophancy.ts`. Patterns are regexes checked against the first 300 characters of each response.

### Use as CLAUDE.md instead

If you prefer CLAUDE.md-based rules over a plugin, copy the content from `agents/thinking.md` (everything below the frontmatter) into your project's `CLAUDE.md`.
