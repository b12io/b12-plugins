# Brand Kit Generator

Tell it your business name and what you do, or attach the logo you already have. It picks the colors and fonts, draws or builds around the logo, and hands over the whole kit in a zip: the logo in full color, one color, reversed and as an icon, a brand board, a printable brand guide, and the colors as CSS.

Every file is built from one brand spec, so the logo, the palette, the guide and the CSS always agree. Change one color and every file follows. No account needed. It can also give you a link to start a B12 website in the same colors.

## Try asking

- Create a brand kit for my business
- Make a brand kit for my bakery
- Build a brand kit around my existing logo

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Brand Kit Generator" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-brand-kit-generator@b12-plugins
  ```

The plugin is a single skill, [`skills/brand-kit-generator/SKILL.md`](skills/brand-kit-generator/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude plus one Python script, `scripts/build_brand_kit.py`, that Claude runs in its code execution to draw the files. The script makes no network calls. It writes a `-brand-kit` folder and a `.zip` to your workspace, sets the logo and brand board in a heading font bundled with the plugin (a free Google Font under the SIL Open Font License, license included), and uses Python's Pillow library for the PNG files when it's installed. When you open `brand-guide.html`, your browser loads the kit's body font from Google Fonts; offline, the guide falls back to a system font. Without Pillow you still get the SVG, HTML, CSS and JSON files. A logo you attach is only read and copied into the kit.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE). The bundled heading fonts are under the [SIL Open Font License](skills/brand-kit-generator/scripts/fonts/).
