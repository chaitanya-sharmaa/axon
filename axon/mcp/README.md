# Agentic Charting via MCP

Axon fully supports enabling your AI agents to draw, validate, and preview native charts using Microsoft's [Flint Chart MCP Server](https://github.com/microsoft/flint-chart).

## Getting Started (Claude Desktop)
If you're using Claude Desktop to interface with your agents, you can inject the Flint Chart MCP server directly into its context:

1. Locate your Claude Desktop configuration file:
   - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
2. Merge the contents of `./claude_desktop_config.json` into your configuration.
3. Restart Claude Desktop.

Claude can now generate ECharts and Vega-Lite charts using the `flint-chart` tools!

## Getting Started (Cursor / Custom Clients)
You can expose the Flint MCP server to any compatible client by spinning it up via `npx`. Add the following configuration to your client's MCP settings:

- **Command:** `npx`
- **Arguments:** `-y`, `flint-chart-mcp`

## Running Programmatically
If you are running your own agent framework (like LangChain or AutoGen), you can connect it via `stdio`:
```bash
npx -y flint-chart-mcp
```
