import asyncio

from openai import AsyncOpenAI

# Point OpenAI client to Axon local bridge
client = AsyncOpenAI(
    api_key="axon-local",
    base_url="http://localhost:8080/v1"
)

async def main():
    print("Agentic Charting Example")
    print("-------------------------")
    print("This example demonstrates how an AI agent can analyze its own telemetry data")
    print("and use the Flint Chart MCP server to visualize the cost savings.")

    # In a real workflow, the agent would fetch this telemetry from the Axon Admin API
    telemetry_data = """
    Date: 2026-06-21, Type: Semantic Cache, Tokens Saved: 150000
    Date: 2026-06-21, Type: Compression, Tokens Saved: 80000
    Date: 2026-06-22, Type: Semantic Cache, Tokens Saved: 180000
    Date: 2026-06-22, Type: Compression, Tokens Saved: 95000
    Date: 2026-06-23, Type: Semantic Cache, Tokens Saved: 210000
    Date: 2026-06-23, Type: Compression, Tokens Saved: 125000
    """

    print("\nPrompting agent to write a Flint chart spec...")

    # We ask the agent to formulate a Flint chart spec.
    # NOTE: If connected directly to the Flint MCP Server (e.g. via Claude Desktop),
    # the agent could use the MCP tools automatically. Here, we just prompt it directly.
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an AI assistant who writes Microsoft Flint Chart specifications (JSON). Output ONLY raw JSON, no markdown formatting. The output should be a ChartAssemblyInput with 'data' and 'chart_spec' defined."},
            {"role": "user", "content": f"Given the following data, write a Flint chart spec that creates a Stacked Bar Chart showing token savings over time, grouped by the optimization type.\n\nData:\n{telemetry_data}"}
        ]
    )

    chart_spec = response.choices[0].message.content
    print("\nGenerated Flint Spec:")
    print(chart_spec)
    print("\n✅ This spec can now be sent to the flint-chart library to render an ECharts or Vega-Lite visualization!")

if __name__ == "__main__":
    asyncio.run(main())
