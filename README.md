# CAB432 Assignment 2 - Track B: Repository Custodian

This repository contains the implementation for the CAB432 Assignment 2 Track B project: a small cloud-native repository custodian built around Amazon Bedrock, MCP tooling, and event-driven AWS workflows.

The system is intentionally scoped to a practical, demonstrable architecture rather than a large multi-agent platform. It supports:

- grounded repository Q&A using documentation and repository context
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

## Core capabilities

### 1. Grounded repository questions

A user can ask questions such as:

- How does authentication work?
- Where is the API configured?
- What is the deployment flow?

The system retrieves relevant repository context from documentation and project files, passes that context to Amazon Bedrock, and answers using the retrieved material rather than relying purely on model memory.

### 2. Asynchronous GitHub issue triage

When a GitHub issue is opened, a webhook-driven workflow processes the issue asynchronously:

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

A recurring EventBridge trigger runs a digest job that inspects completed triage results and produces a concise daily summary stored in DynamoDB for later retrieval by the UI.

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

## Repository layout

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

## Configuration expectations

The final implementation should follow the assignment requirements:

- deploy in `ap-southeast-2`
- tag all AWS resources with the required QUT username and purpose tag
- keep secrets out of source code and plaintext environment files
- use a small, bounded repository and documentation set for demonstration
- keep the design practical and easy to explain during the oral presentation

## Submission considerations

This repository should be able to support the assignment submission requirements, including:

- a functioning chat interface conversation
- one or more retrieval-grounded answers
- an asynchronous workflow triggered by an issue event
- evidence of a scheduled autonomous run
- clear documentation of the deployed infrastructure and components

## Notes

This project is intentionally not a large coding-agent platform. The goal is a small, complete, cloud-deployed, demonstrable assistant designed around repository context, Bedrock, and AWS-managed services.

---

This README is intended to describe the project at a high level and provide the context needed for implementation and demonstration.
