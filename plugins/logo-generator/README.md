# Logo Generator

Say what the logo is for, and give a business name only if you want one in the design. It draws the logo, shows you a preview, and hands over the files in a zip — SVG and PNG, as a horizontal lockup plus a square icon for avatars and favicons when there is a name, or a text-free mark when there isn't. Then it can generate a matching B12 website using the same brand colors.

## Try asking

- Design a logo for my company
- I need a logo for my coffee shop
- Create a modern logo

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Logo Generator" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-logo-generator@b12-plugins
  ```

The plugin is a single skill, [`skills/logo-generator/SKILL.md`](skills/logo-generator/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own. It writes SVG and PNG files to your workspace and packs them into a zip. PNGs are rendered with whatever converter is already installed, such as `cairosvg` or `rsvg-convert`.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
