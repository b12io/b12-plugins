# PDF: Make, Research, Summarize

Describe the document you need — proposals, invoices, reports, one-pagers — and it builds the whole thing as a real PDF. Or attach a PDF you already have and it reads that instead: answering questions with page numbers, pulling out tables, summarizing, comparing two versions.

Every fact traces to your own words or to a page you supplied, and anything else is left as a marked placeholder rather than quietly invented. It researches the PDFs you hand it, not the web. You get an editable .pdf, no account needed and nothing uploaded. Ask for a matching website too and you'll get a free B12 website link.

## Try asking

- Make a client proposal as a PDF
- Summarize this PDF with page citations
- Compare these two contract versions

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "PDF: Make, Research, Summarize" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-pdf-make@b12-plugins
  ```

The plugin is a single skill, [`skills/pdf-make/SKILL.md`](skills/pdf-make/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own other than the one package install described here. It reads PDFs you attach and writes `.pdf` files to your workspace, using Python in Claude's code execution. If `reportlab`, `pdfplumber`, or `pypdf` is missing, it makes one attempt to install it from PyPI and otherwise falls back to other tools.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
