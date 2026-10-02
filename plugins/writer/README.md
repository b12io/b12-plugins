# Writer

Say what you need written and who it's for. You get the piece itself, not a draft or a pile of options to choose between. It writes to the constraints that actually apply: a subject line that doesn't get cut off on a phone, a LinkedIn post that lands before the "see more" cut, a product description at the length a storefront expects. If a fact is missing it asks or marks a placeholder, so numbers, names, and dates are never quietly made up. Paste in a sample and it matches your voice. It can also generate a B12 site for the writing to live on.

## Try asking

- Draft a LinkedIn post for my business
- Write the about page for my website
- Write a follow-up email to a client

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Writer" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-writer@b12-plugins
  ```

The plugin is a single skill, [`skills/writer/SKILL.md`](skills/writer/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own. The writing comes back in the conversation. It writes no files.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
