# CAB432 Assignment 2 - Track B: Repository Custodian

This repository is being developed for the CAB432 Assignment 2 Track B project: a small cloud-native repository custodian built around Amazon Bedrock, MCP tooling, and event-driven AWS workflows. It contains the original Strobe Python server, the supplied ACP chat client, and the retrieval/indexing module with its MCP server. The grounded ACP mode is implemented, but live model inference is currently blocked by an AWS service control policy; issue triage, scheduled digests, and cloud deployment remain planned work.

The intended system is deliberately scoped to a practical, demonstrable architecture rather than a large multi-agent platform. It brings together the implemented repository retrieval and MCP path with these capabilities:

- grounded repository Q&A using documentation and repository context (agent wired; live inference blocked)
- asynchronous GitHub issue triage
- scheduled daily repository digest generation
- a conversational frontend for interacting with the agent

## Project purpose

The goal is to help a repository owner manage incoming GitHub issues and answer repository questions using AI grounded in repository context, while keeping the solution small, cloud-native, and easy to demonstrate.

The system is designed around:

- an MCP server that exposes repository-focused tools
- a conversational agent that calls the MCP server and Bedrock
- asynchronous background processing for GitHub issue triage
- scheduled automation for regular digests and maintenance-style runs

## Core capabilities and roadmap

### 1. Grounded repository questions

The repository-grounded ACP mode retrieves relevant indexed documentation through the MCP server and sends it to Amazon Bedrock for an answer with source paths and line ranges. A live grounded chat has been verified using NVIDIA Nemotron 3 Super 120B. This model accepts text only; use deterministic mode to exercise the supplied ACP client's inline image handling. Example questions include "How does authentication work?", "Where is the API configured?", and "What is the deployment flow?"

### 2. Asynchronous GitHub issue triage

The planned issue-triage workflow will process opened GitHub issues asynchronously:

- webhook validation and ingestion
- queue-based processing
- issue classification using Bedrock
- persistence of triage results in DynamoDB

Example output includes:

- category
- priority
- summary
- processingStatus

### 3. Scheduled daily digest

The planned EventBridge schedule will invoke a digest job that reads completed triage results and stores a concise daily summary in DynamoDB for retrieval by the UI.

## Recommended architecture

The solution follows the Track B design expectations:

- Amazon Bedrock for model access
- Amazon S3 Vectors for retrieval over repository context
- MCP server as a distinct repository tool layer
- ACP-compatible web UI for chat interaction
- AWS Lambda for webhook and background processing
- Amazon SQS for asynchronous issue handling
- Amazon EventBridge for scheduled automation
- DynamoDB for issue and digest records
- ECS Fargate for the runtime components
- Secrets Manager for credentials

## High-level flow

```text
Browser UI
  -> ACP agent
      -> MCP server tools
      -> Bedrock + repository context

GitHub issue webhook
  -> API Gateway / Lambda
  -> SQS
  -> Triage Lambda
  -> Bedrock classification
  -> DynamoDB

EventBridge schedule
  -> Digest Lambda
  -> Bedrock summary generation
  -> DynamoDB
```

## Intended component layout

```text
repository-custodian/
  agent-server/
  mcp-server/
  functions/
    webhook_handler/
    triage_handler/
    digest_handler/
  webui/
  local/
  docs/
  README.md
```

## Local development

This repository is intended to be developed as a cloud-focused project. Local development may include:

1. running the supplied ACP web client and its deterministic test agent
2. running the MCP server locally for tool access
3. running the agent service locally for command and chat testing
4. validating the webhook and triage flow with mocked payloads

### ACP chat client

The `webui/` directory contains the ACP WebUI supplied for the CAB432 practical, including its deterministic agent for local client testing. The deterministic agent is only a protocol/UI test fixture; it does not call Bedrock or access repository data.

The grounded ACP mode is selected with `AGENT_MODE=bedrock` and requires the local MCP server plus AWS permission to invoke the configured Bedrock model. Its default is `nvidia.nemotron-super-3-120b`. See [`webui/README.md`](webui/README.md) for setup instructions; deterministic mode remains the default for tests.

With Node.js installed, start the client and deterministic agent in separate terminals:

```bash
cd webui
npm ci
npm run server
```

```bash
cd webui
npm run dev
```

Open the local URL printed by Vite. The supplied client currently connects to `ws://127.0.0.1:7331/acp`. The production endpoint will be configured when the ACP agent and frontend deployment are wired together.

### Repository context retrieval

`repository_context.py` indexes a small, curated set of existing project documentation into the Assignment 2 S3 Vectors index and searches it using Amazon Bedrock text embeddings. It includes the root project README, the supplied ACP client README, the Strobe server README, and the Strobe Insomnia API description. It does not index source files, credentials, or the whole repository.

The configured index uses 1024-dimensional cosine vectors and Amazon Titan Text Embeddings V2. From the repository root, authenticate to AWS and install the custodian dependencies:

```bash
python -m pip install -r requirements.txt
python repository_context.py index
python repository_context.py search "How does authentication work?"
```

Indexing makes Bedrock embedding requests and writes or replaces vectors with the `repo-custodian/` key prefix in the existing index. Search returns the closest document chunks with their source paths and line ranges.

The same module exposes repository search as an MCP tool. Run it as a separate process from the agent:

```bash
python repository_context.py serve
```

The server uses Streamable HTTP at `http://127.0.0.1:3001/mcp` by default and binds to loopback so the MCP endpoint is not exposed on other network interfaces. `MCP_HOST` and `MCP_PORT` can override its bind address and port for a suitably restricted deployment. The `search_repository_context` tool returns matching source excerpts with line ranges.

## Configuration expectations

The final implementation should follow the assignment requirements:

- deploy in `ap-southeast-2`
- tag all AWS resources with the required QUT username and purpose tag
- keep secrets out of source code and plaintext environment files
- use a small, bounded repository and documentation set for demonstration
- keep the design practical and easy to explain during the oral presentation

## Submission considerations

The completed project will need to demonstrate the assignment requirements, including:

- a functioning chat interface conversation
- one or more retrieval-grounded answers
- an asynchronous workflow triggered by an issue event
- evidence of a scheduled autonomous run
- clear documentation of the deployed infrastructure and components

## Notes

This project is intentionally not a large coding-agent platform. The goal is a small, complete, cloud-deployed, demonstrable assistant designed around repository context, Bedrock, and AWS-managed services.

---

This README is intended to describe the project at a high level and provide the context needed for implementation and demonstration.
