export const dynamic = 'force-static'
export const revalidate = 86400

export function GET() {
  const content = `# 灵犀 Lingxi

> Sim is the open-source AI workspace where teams build, deploy, and manage AI agents. Connect 1,000+ integrations and every major LLM to create agents that automate real work.

Sim lets teams create agents visually with the workflow builder, conversationally through Chat, or programmatically with the API. The workspace includes knowledge bases, tables, files, and full observability.

## Preferred URLs

- [Homepage](/): 灵犀产品首页
- [Workspace](/workspace/lingxi/home): 灵犀工作区

## Documentation

- [Documentation](https://docs.sim.ai): Product guides and technical reference
- [Quickstart](https://docs.sim.ai/getting-started): Fastest path to getting started
- [API Reference](https://docs.sim.ai/api-reference): API documentation

## Key Concepts

- **Workspace**: The AI workspace — container for agents, workflows, data sources, and runs
- **Workflow**: Visual builder — directed graph of blocks defining agent logic
- **Block**: Individual step such as an LLM call, tool call, HTTP request, or code execution
- **Trigger**: Event or schedule that initiates a workflow run
- **Execution**: A single run of a workflow with logs and outputs
- **Knowledge Base**: Document store used for retrieval-augmented generation

## Capabilities

- AI workspace for teams
- AI agent creation and deployment
- Integrations across business tools, databases, and communication platforms
- Multi-model LLM orchestration
- Knowledge bases and retrieval-augmented generation
- Table creation and management
- Document creation and processing
- Scheduled and webhook-triggered runs

## Use Cases

- AI agent deployment and orchestration
- Knowledge bases and RAG pipelines
- Customer support automation
- Internal operations workflows across sales, marketing, legal, and finance

## Additional Links

- [GitHub Repository](https://github.com/simstudioai/sim): Open-source codebase
- [Docs](https://docs.sim.ai): Canonical documentation source
- [Terms of Service](/terms): 服务条款
- [Privacy Policy](/privacy): 隐私政策
`

  return new Response(content, {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Cache-Control': 'public, max-age=86400, s-maxage=86400',
    },
  })
}
