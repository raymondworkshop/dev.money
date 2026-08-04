# macOS LaunchAgents for dev.business

## Publish (sync + deploy)

`com.zhaowenlong.dev-business.publish.plist` runs Mon 00:00 and Wed 00:00:

1. Wait for local-gateway at `LLM_URL` (default `http://127.0.0.1:8080`)
2. `make sync` with `LLM_PROVIDER=local-gateway`, `LLM_MODEL=gemma4`, fallback model `mlx`
3. `make site-deploy` to Cloudflare Pages (`DEPLOY=1`)

### Install

```bash
mkdir -p /Users/zhaowenlong/workspace/dev.business/logs
cp launchd/com.zhaowenlong.dev-business.publish.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.zhaowenlong.dev-business.publish.plist
```

Or: `make launchd`

### Prerequisites

- Local gateway: `~/Library/LaunchAgents/com.user.llmgateway.plist`
- MLX (fallback model): `~/Library/LaunchAgents/com.user.mlxserver.plist`
- `.env` with gateway URL / model settings
- Wrangler: `npx wrangler login` or `CLOUDFLARE_API_TOKEN` in environment

### Manual test

```bash
make launchd ACTION=test
# or
make publish
```

### Unload

```bash
make launchd ACTION=unload
```
