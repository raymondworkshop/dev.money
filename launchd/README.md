# macOS LaunchAgents for dev.business

## Publish (sync + deploy)

`com.zhaowenlong.dev-business.publish.plist` runs weekly:

1. Wait for local MLX at `http://127.0.0.1:8080`
2. `make sync` with `LLM_PROVIDER=mlx`
3. `make site-deploy` to Cloudflare Pages

### Install

```bash
mkdir -p /Users/zhaowenlong/workspace/dev.business/logs
cp launchd/com.zhaowenlong.dev-business.publish.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.zhaowenlong.dev-business.publish.plist
```

### Prerequisites

- MLX server: `~/Library/LaunchAgents/com.user.mlxserver.plist`
- `.env` with `LLM_PROVIDER=mlx`
- Wrangler: `npx wrangler login` or `CLOUDFLARE_API_TOKEN` in environment

### Manual test

```bash
make publish
```

### Unload

```bash
launchctl bootout gui/$(id -u)/com.zhaowenlong.dev-business.publish
```
