# Presentation Generator

Describe the deck you need, from pitch decks to quarterly reviews, and it builds the whole thing: the argument first, then slides that back it up, with real detail kept in the speaker notes and no invented numbers.

You get an editable .pptx or a browser-ready HTML deck, no account needed and nothing uploaded. Ask for a matching website too, and you'll get a free B12 website link in the same colors.

## Try asking

- Create a pitch deck for my startup
- Make a sales deck for my services
- Build a training deck for new hires

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Presentation Generator" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-presentation-generator@b12-plugins
  ```

The plugin is a single skill, [`skills/presentation-generator/SKILL.md`](skills/presentation-generator/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own other than the one package install described here. It writes an editable `.pptx` to your workspace using Python in Claude's code execution. If `python-pptx` is missing, it makes one attempt to install it from PyPI, and otherwise builds a self-contained HTML deck instead.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
