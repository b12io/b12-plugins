# Designer

Say what page you need and what your business does, and it designs it, then hands you a single HTML file you can open and look at. It tells you why, too: the palette in hex, the fonts it paired, what the layout's trying to get a visitor to do. So if something feels off, you know what to push back on.

It also gives you two other versions of the page to compare, so you're not stuck with the first pass. Once you've found the one you want, it can generate a hosted website on B12 in the same colors.

## Try asking

- Design a homepage for my business
- Design a pricing page
- Make this page look more premium

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Designer" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-designer@b12-plugins
  ```

The plugin is a single skill, [`skills/designer/SKILL.md`](skills/designer/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own. It writes one self-contained `.html` file to your workspace, plus up to two variant files for comparison.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
