# B12 Claude Plugin

This plugin includes two skills that help you build and manage websites on B12 using Claude.

## Skills

### Website Generator

Creates a production-ready B12 website from a brief description. Claude will ask for a description of your project or business (goals, structure, style, etc.) and generate a signup link with a pre-built site ready to publish.

**Example prompts:**
```
"Create a website for a consulting firm"
"Create a website for a software development agency"
"Create a personal website"
"Create a website for a cat café"
```

### B12 Website Editor

Edits and improves a live B12 website using Claude's browser access. Claude can take screenshots, scroll, click, and type directly into the B12 editor to apply design changes, add sections, rewrite copy, and build web app features.

> Requires browser access — only works in Claude Cowork (Claude in Chrome extension).

**Example prompts:**
```
"Edit my B12 website"
"Make my site look like a premium luxury brand"
"Add a pricing section with 3 tiers"
"Redesign the hero section"
```

## Installation

### Claude.ai

Install each skill individually:

**Website Generator**
1. Download [website-generator.zip](website-generator.zip)
2. Go to **claude.ai** > **Settings** > **Skills**
3. Upload the zip file

**B12 Website Editor**
1. Download [b12-website-editor.zip](b12-website-editor.zip)
2. Go to **claude.ai** > **Settings** > **Skills**
3. Upload the zip file

### Claude Code

Via the marketplace (recommended):
```bash
claude plugin marketplace add b12io/b12-claude-plugin
claude plugin install b12-claude-plugin@b12-plugins
```

Or load directly from a local clone:
```bash
claude --plugin-dir /path/to/b12-claude-plugin
```

### Claude Cowork

Install through the plugin manager in Claude Desktop.

### Kimi Code CLI

The **Website Generator** skill also runs on Kimi Code. Install directly from GitHub:

```
/plugins install https://github.com/b12io/b12-claude-plugin
```

After installing, run `/reload` or start a fresh session with `/new`.

> The **B12 Website Editor** skill is not available on Kimi Code — it requires browser access, which is only available in Claude Cowork.

## License

Apache 2.0
