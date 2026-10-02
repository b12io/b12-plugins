# Code

Ask for code and get code — a complete file, a working component, a whole corrected block — in whatever language or framework you name. It writes the parts most assistants skip. No "rest of the code goes here," every import in place, and a plain note about what the code still needs before it runs, whether that's an install command, a key you have to supply, or the backend a contact form won't work without. Paste a snippet in for review or unit tests and the full block comes back, not a list of line edits. And when you'd rather have the finished thing than the source, it can generate a web app or website on B12.

## Try asking

- Generate a web app
- Create a landing page in HTML, CSS, and JavaScript
- Review this code snippet

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Code" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-code@b12-plugins
  ```

The plugin is a single skill, [`skills/code/SKILL.md`](skills/code/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own. Code comes back in the conversation. It writes no files unless you ask it to save one.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
