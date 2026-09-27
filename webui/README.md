# ACP Chat Web Client

This folder contains a small browser client for the [Agent Client Protocol](https://agentclientprotocol.com), a deterministic ACP agent for local testing, and an optional repository-grounded agent.

The browser connects directly to the ACP agent over WebSocket. The deterministic agent is the default and does not call a model. The repository-grounded mode retrieves excerpts through the project's MCP server and uses Amazon Bedrock Converse to answer questions with source paths and line ranges.

## Run locally

From this directory:

```bash
npm install

# Terminal 1: deterministic ACP agent
npm run server

# Terminal 2: Vite development server
npm run dev
```

Open <http://127.0.0.1:5173/>. The client connects automatically to the endpoint set near the top of `web/main.ts`:

```text
ws://127.0.0.1:7331/acp
```

Ask the agent to `show me an image` to exercise both native ACP image content and the Markdown image fallback. The deterministic server also exposes the image at `/deterministic-image.svg` and a health check at `/healthz`.

## Repository-grounded mode

The grounded agent requires the repository MCP server, valid AWS credentials, and access to the configured Bedrock model. Start the MCP server from the repository root, then start the ACP server from this directory:

```powershell
# Terminal 1, repository root
python repository_context.py serve

# Terminal 2, webui
$env:AGENT_MODE = "bedrock"
$env:AWS_REGION = "ap-southeast-2"
$env:MCP_ENDPOINT = "http://127.0.0.1:3001/mcp"
npm run server
```

The default model is `nvidia.nemotron-super-3-120b`; set `BEDROCK_MODEL_ID` to override it. This model accepts text only, so the grounded agent rejects image prompts rather than pretending the model has analyzed them. Use deterministic mode to exercise the ACP client's image handling, or configure a Bedrock model that accepts images. Unsupported image formats or MCP/Bedrock errors are reported rather than replaced with deterministic answers. Unset `AGENT_MODE` (or set it to `deterministic`) to use the test agent.

Students can edit the visible text directly in `index.html`: the page title, heading, subtitle, initial messages-pane text, placeholder, button labels, and theme labels are all there. The only client setting in TypeScript is the marked `ACP_WEBSOCKET_ENDPOINT` constant at the top of `web/main.ts`.

The endpoint must be reachable directly by the browser; the image does not proxy or start an ACP agent.

## Docker

```bash
docker build -f webui/Dockerfile --target webui -t repo-custodian-webui .
docker build -f webui/Dockerfile --target agent -t repo-custodian-agent .
docker build -f webui/Dockerfile --target mcp -t repo-custodian-mcp .
```

The production multi-stage Dockerfile is built from the repository root and has `webui`, `agent`, and `mcp` targets. The frontend selects a same-origin `wss://` endpoint and its Nginx server proxies `/acp` to the agent in the ECS task. The development build continues to use `ws://127.0.0.1:7331/acp`. The theme toggle switches between light and dark mode and remembers the choice in the browser; the default behavior follows the system theme.

When the deterministic server is bound to all interfaces, set the public origin used in its image Markdown response:

```bash
PUBLIC_ORIGIN=http://localhost:7331 npm run server -- --host 0.0.0.0
```

## Development commands

```bash
npm run dev       # Vite development server
npm run server    # ACP server (deterministic by default, grounded with AGENT_MODE=bedrock)
npm test          # unit tests for the ACP agents and image handling
npm run build     # production bundle and TypeScript check
```

## Scope

The client implements the small subset needed for ordinary conversations:

- ACP initialization and session creation
- streamed assistant text
- native assistant image content
- user image attachments (attach an image to send alongside text)
- Markdown rendering with sanitization
- cancellation
- display of agent thinking/tool activity as status text

It intentionally does not implement filesystem access, terminal sessions, code diffs, authentication, or persistent session loading. The deterministic server rejects permission requests rather than granting them automatically.
