# Deploy dev.business Wiki

This site publishes the curated wiki in `business/wiki` through Quartz.

## Cloudflare Pages Git Integration

Use these settings in Cloudflare Pages:

- Framework preset: `None`
- Build command: `make site-install && make site-build`
- Build output directory: `site/public`
- Root directory: `/`
- Environment variable: `NODE_VERSION=22`

Only the generated static site is published. Do not publish `business/raw`,
`business/raw/archive`, `.env`, or local LLM outputs unless intentionally reviewed.

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

The default Cloudflare Pages project name is `dev-business-wiki`. Override it with:

```bash
make site-deploy PAGES_PROJECT=your-project-name
```
