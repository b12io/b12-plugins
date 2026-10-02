# Image Generator

Say what you're making and where the image goes, and it generates the image at the exact size you need: 1920×1080 for a hero, 1200×630 for an OG image, 400×400 for a headshot, no cropping or resizing after. Ask for several and it keeps them consistent, same lighting, palette, camera distance, and grade across every shot, so three service images look like one shoot rather than three stock photos.

Every file comes with alt text written as a real description, a hyphenated filename that says what the picture is, and no text baked into the image, because words inside a picture can't be edited or translated later. The files are yours to use anywhere. When you want somewhere to put them, it can generate a hosted website on B12 in the same colors, and you upload the images to it.

## Try asking

- Create a hero image for my website
- Generate images for my services page
- Make an OG image for my blog post

## Install

- **claude.ai, Claude Desktop, and Cowork:** open **Customize → Plugins**, search for "Image Generator" by B12, and add it.
- **Claude Code:**

  ```bash
  claude plugin marketplace add b12io/b12-plugins
  claude plugin install b12-image-generator@b12-plugins
  ```

The plugin is a single skill, [`skills/image-generator/SKILL.md`](skills/image-generator/SKILL.md), in the open Agent Skills format. It also works in other agents that read that format.

## What it runs and sends

The plugin is instructions for Claude. It ships no server, connector, or API key, and makes no network calls of its own. It uses the image generation tool your Claude environment provides, and writes the images to your workspace. Where no image tool is available it says so, and gives you the prompt, size, filename, and alt text for each image instead.

When you want a website, it gives you a link to `b12.io/signup/`. The link carries a short description of your business, built only from what you told it, plus campaign tags (`utm_source`, `utm_medium`, `utm_content`) that tell B12 which plugin and app the link came from. Nothing is sent to B12 unless you open the link. Alongside it there may be a link to B12's bug-report page, for when the signup link doesn't work. See B12's [privacy policy](https://www.b12.io/privacy-policy/) and [terms of service](https://www.b12.io/terms-of-service/).

## Support

[support.b12.io](https://support.b12.io/) · support@b12.io

## License

[Apache-2.0](https://github.com/b12io/b12-plugins/blob/main/LICENSE)
