# Deploy dev.news-wiki

This site publishes the curated wiki in `newswiki/wiki` through Quartz.

## Cloudflare Pages Git Integration

Use these settings in Cloudflare Pages:

- Framework preset: `None`
- Build command: `make site-install && make site-build`
- Build output directory: `site/public`
- Root directory: `/`
- Environment variable: `NODE_VERSION=22`

Only the generated static site is published. Do not publish `newswiki/raw`,
`newswiki/raw/archive`, `.env`, or local LLM outputs unless intentionally reviewed.

## Manual Deploy

From the repository root:

```bash
make site-install
make site-deploy
```

If Wrangler asks you to authenticate:

```bash
npx wrangler login
```

The default Cloudflare Pages project name is `news-wiki`. Override it with:

```bash
make site-deploy PAGES_PROJECT=your-project-name
```
