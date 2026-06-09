# dev.news-wiki Quartz Site

This Quartz scaffold renders the curated news wiki as a static website.

Source of truth:

- `../newswiki/wiki`

Generated and unpublished:

- `content/`
- `public/`
- `node_modules/`

Common commands from the repository root:

```bash
make site-install
make site-build
make site-serve
```

Deploy only the generated `site/public` directory. Do not publish `newswiki/raw`,
`newswiki/raw/archive`, API keys, or local output files unless intentionally reviewed.
