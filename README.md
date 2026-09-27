# CAB432 Assignment 2 - Track B: Repository Custodian

This repository is being developed for the CAB432 Assignment 2 Track B project: a small cloud-native repository custodian built around Amazon Bedrock, MCP tooling, and event-driven AWS workflows. It contains the original Strobe Python server, the supplied ACP chat client, curated repository retrieval with its MCP server, and the grounded ACP agent. Grounded chat was verified with NVIDIA Nemotron 3 Super 120B. The asynchronous issue-triage path is deployed and has processed a controlled, signed synthetic issue end to end; the GitHub repository webhook itself has not yet been configured.

The intended system is deliberately scoped to a practical, demonstrable architecture rather than a large multi-agent platform. It brings together the implemented repository retrieval and MCP path with these capabilities:

- grounded repository Q&A using documentation and repository context
- asynchronous GitHub issue triage (deployed and end-to-end tested with a synthetic issue)
- scheduled daily repository digest generation (handler implemented; schedule setup in progress)
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

`issue_triage.py` implements the webhook and SQS worker entry points. The deployed regional API Gateway endpoint is `https://tkjwq24v4g.execute-api.ap-southeast-2.amazonaws.com/prod/webhook`. It invokes the webhook Lambda, which verifies GitHub's SHA-256 HMAC using a dedicated Secrets Manager webhook secret, filters for opened issues, and queues a bounded issue payload. The SQS worker classifies the issue with Bedrock, validates the response fields, and stores a single idempotent result in the project's tagged DynamoDB table. A tagged SQS dead-letter queue handles messages that exceed the retry limit. The synthetic signed-event test traversed the API, both Lambdas, SQS, Bedrock, and DynamoDB successfully. Local unit tests use fake AWS clients; no GitHub PAT is used by this inbound webhook flow.

The Phase 5 resources in `ap-southeast-2` are `n12550281-repo-custodian-issues`, `n12550281-repo-custodian-triage`, `n12550281-repo-custodian-triage-dlq`, `n12550281-repo-custodian-webhook`, `n12550281-repo-custodian-triage-worker`, and the `n12550281-repo-custodian-webhook-rest` API (`prod` stage). The webhook HMAC secret is `n12550281-repo-custodian-webhook`. All are tagged with the project QUT username and `purpose=assessment 2`.

The GitHub repository webhook is not configured yet. When ready, configure an `issues` webhook for opened events to the endpoint above and use the `SecretString` from the dedicated webhook secret in Secrets Manager. Keep that value out of source control and messages.

Example output includes:

- category
- priority
- summary
- processingStatus

### 3. Scheduled daily digest

`issue_triage.py` includes an EventBridge digest handler. It reads completed issue records from the last 24 hours, asks the configured Bedrock model for a concise evidence-bounded summary, and stores one digest per Brisbane calendar day in the existing tagged agent-run table. Repeated invocations for the same day do not create duplicate digest records. The local unit tests cover populated and empty digest windows, persistence, and duplicate handling; the daily EventBridge schedule remains to be configured.

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
- Secrets Manager for the GitHub webhook HMAC secret (no GitHub PAT is needed for inbound issue events)

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

### Local issue-triage tests

Run the standard-library unit tests from the repository root. They exercise HMAC verification, opened-issue enqueueing, invalid payload rejection, Bedrock result validation, idempotent issue processing, SQS partial batch failure reporting, and daily digest generation without making AWS calls:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

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
