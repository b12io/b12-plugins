# Blog Generator

Tell the plugin about your blog audience and the topics you want to cover, and it will generate a ready to publish blog site on B12 — hosting, design, and layout handled. Built for service businesses and professionals who want to start publishing without setting up a website first.

## Try asking

- Create a blog for my accounting firm
- I want to start a blog for new dog owners
- Set up a blog for my law practice about estate planning

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Blog Generator" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-blog-generator@b12-plugins
  ```

The plugin is a single skill, [`skills/blog-generator/SKILL.md`](skills/blog-generator/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own. It writes no files. What you get is a B12 signup link that opens a blog site built from your answers.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
