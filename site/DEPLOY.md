<<<<<<< HEAD
# Deploy dev.news-wiki
=======
# Deploy dev.business Wiki
>>>>>>> 5aebb7ac6aa114fc313bf33f93ffb12cb9425862

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

<<<<<<< HEAD
The default Cloudflare Pages project name is `news-wiki`. Override it with:

```bash
make site-deploy PAGES_PROJECT=your-project-name
=======
Production URL: **https://news-wiki.pages.dev/**

The default Cloudflare Pages project name is `news-wiki` (branch `master`). Override with:

```bash
make site-deploy PAGES_PROJECT=your-project-name PAGES_BRANCH=main
```

## Sync Then Deploy

After MLX sync updates `newswiki/wiki`, publish the site in one step:

```bash
make publish
```

Sync only (no deploy):

```bash
make publish DEPLOY=0
```

Requires:

- MLX server running (`LLM_PROVIDER=mlx` in `.env`)
- `make site-install` on first run (handled automatically by `scripts/publish.sh`)
- Wrangler auth (`npx wrangler login` or `CLOUDFLARE_API_TOKEN`)

## macOS Scheduled Publish

Copy the LaunchAgent template and load it:

```bash
mkdir -p logs
cp launchd/com.zhaowenlong.dev-business.publish.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.zhaowenlong.dev-business.publish.plist
```

Default schedule: **Tuesday 01:30**. Logs: `logs/launchd-publish.{out,err}.log`.

Prerequisites for unattended runs:

1. `com.user.mlxserver` LaunchAgent loaded (local LLM)
2. Wrangler credentials available to launchd (API token recommended)
3. `site/node_modules` installed, or allow first-run `make site-install`

Test manually:

```bash
scripts/publish.sh
>>>>>>> 5aebb7ac6aa114fc313bf33f93ffb12cb9425862
```
