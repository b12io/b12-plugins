# Diagram Builder

Describe how your work actually flows — the steps, the people, the handoffs — and it draws the diagram: process flows, swimlanes, decision trees, org charts, timelines and journey maps, with every arrow labeled and nothing invented.

You get a real .svg file in your brand colors, sharp at any size, no account needed and nothing uploaded. Ask for a matching website too, and you'll get a free B12 website link in the same colors.

## Try asking

- Map our client onboarding from first enquiry to kickoff call
- Turn our intake process into a flowchart for our services page
- Draw a swimlane showing what we handle and what the client handles

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Diagram Builder" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-diagram-builder@b12-plugins
  ```

The plugin is a single skill, [`skills/diagram-builder/SKILL.md`](skills/diagram-builder/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own. It writes an `.svg` file to your workspace. When a converter such as `rsvg-convert` or `cairosvg` is already installed, it also renders a PNG preview. It doesn't install one.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
