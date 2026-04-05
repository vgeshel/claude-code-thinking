# claude-thinking

A Claude Code plugin that enforces deliberate thinking, eliminates sycophancy, and improves response quality.

## What it does

When enabled, this plugin changes how Claude Code works:

1. **Deliberation checklist** — Before every substantive response, Claude works through 5 questions: What is being asked? What does a complete solution require? What do I not know? Does this conflict with anything? How will I verify this works?

2. **Zero sycophancy** — Blocks reflexive agreement phrases ("you're right", "good point", "great idea"). These are a canary for shallow thinking — if Claude is agreeing without examining, it hasn't evaluated deeply enough. Note: the sycophancy patterns currently match English phrases only.

3. **Behavioral rules** — Think before acting, verify your own work, fix all problems (no "low priority" excuses), answer questions before jumping to action, finish everything the user asked for.

## How it works

The plugin has two parts:

- **Default agent** (`agents/thinking.md`) — Applies the thinking rules as a system prompt to every conversation. This is always active when the plugin is enabled.
- **Stop hooks** (`hooks/`) — Python scripts that mechanically block responses containing sycophantic phrases or lacking the `_I THOUGHT_` deliberation marker. These catch violations that slip through the system prompt.

## Install

```bash
claude plugin marketplace add vgeshel/claude-code-thinking --scope project
claude plugin install claude-thinking --scope project
```

The first command adds the marketplace. The second installs the plugin from it. `--scope project` stores the configuration in the project so all contributors get it.

## Requires

- Python 3 — the hooks are Python scripts

The plugin checks for `python3` on session start and prints a warning if it's missing.

## Run tests

```bash
cd hooks && python3 -m unittest -v
```

## Customization

### Disable the thinking marker

If the `_I THOUGHT_` marker is too noisy for your workflow, remove the `check_thinking.py` hook from `hooks/hooks.json`. The behavioral rules from the agent will still apply.

### Add sycophancy patterns

Edit the `SYCOPHANCY_PATTERNS` list in `hooks/check_sycophancy.py`. Patterns are regexes checked against the first 300 characters of each response.

### Use as CLAUDE.md instead

If you prefer CLAUDE.md-based rules over a plugin, copy the content from `agents/thinking.md` (everything below the frontmatter) into your project's `CLAUDE.md`.
