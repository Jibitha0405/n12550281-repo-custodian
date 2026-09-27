import { describe, expect, it } from "vitest";
import * as acp from "@agentclientprotocol/sdk";
import {
  DeterministicAgent,
  chunkText,
  extractPromptText,
  formatRetrievedContext,
  imageFormat,
  isKnownTextOnlyBedrockModel,
  parseRepositoryDocuments,
} from "../server/deterministic-acp";

describe("deterministic ACP agent", () => {
  it("extracts text blocks and ignores other prompt content", () => {
    expect(
      extractPromptText([
        { type: "text", text: "hello" },
        { type: "image", data: "AAAA", mimeType: "image/png" },
        { type: "text", text: "world" },
      ]),
    ).toBe("hello\nworld");
  });

  it("chunks text without changing its contents", () => {
    const chunks = chunkText("abcdef", 2);
    expect(chunks).toEqual(["ab", "cd", "ef"]);
    expect(chunks.join("")).toBe("abcdef");
  });

  it("parses MCP excerpts and formats deduplicated source citations", () => {
    const documents = [
      { source: "README.md", line_start: 10, line_end: 14, text: "Repository overview" },
      { source: "README.md", line_start: 10, line_end: 14, text: "Repository overview" },
    ];

    expect(parseRepositoryDocuments([
      { type: "text", text: JSON.stringify(documents) },
    ])).toEqual(documents);
    expect(formatRetrievedContext(documents)).toBe(
      "Repository context retrieved from:\n- README.md:10-14",
    );
  });

  it("maps Bedrock image formats and rejects unsupported types", () => {
    expect(imageFormat("image/jpeg")).toBe("jpeg");
    expect(imageFormat("image/png")).toBe("png");
    expect(() => imageFormat("image/svg+xml")).toThrow("does not support");
  });

  it("marks the configured NVIDIA model as text-only", () => {
    expect(isKnownTextOnlyBedrockModel("nvidia.nemotron-super-3-120b")).toBe(true);
    expect(isKnownTextOnlyBedrockModel("amazon.nova-2-lite-v1:0")).toBe(false);
  });

  it("rejects malformed MCP document payloads", () => {
    expect(() => parseRepositoryDocuments([
      { type: "text", text: JSON.stringify({ source: "README.md" }) },
    ])).toThrow("invalid shape");
  });

  it("returns deterministic text and native image content", async () => {
    const agent = new DeterministicAgent("http://127.0.0.1:7331/deterministic-image.svg", 0);
    const session = agent.newSession({ cwd: "/", mcpServers: [] });
    const updates: acp.SessionNotification[] = [];
    const context = {
      notify: async (_method: string, params: acp.SessionNotification) => {
        updates.push(params);
      },
    } as unknown as acp.AgentContext;

    const result = await agent.prompt(
      {
        sessionId: session.sessionId,
        prompt: [{ type: "text", text: "show me an image" }],
      },
      context,
    );

    expect(result).toEqual({ stopReason: "end_turn" });
    const hasImage = updates.some((item) => {
      const update = item.update;
      return update.sessionUpdate === "agent_message_chunk" && update.content.type === "image";
    });
    expect(hasImage).toBe(true);
    const text = updates.flatMap((item) => {
      const update = item.update;
      return update.sessionUpdate === "agent_message_chunk" && update.content.type === "text"
        ? [update.content.text]
        : [];
    }).join("");
    expect(text).toContain("Deterministic reply #1");
    expect(text).toContain("Markdown");
  });

  it("acknowledges and echoes an uploaded image", async () => {
    const agent = new DeterministicAgent("http://127.0.0.1:7331/deterministic-image.svg", 0);
    const session = agent.newSession({ cwd: "/", mcpServers: [] });
    const updates: acp.SessionNotification[] = [];
    const context = {
      notify: async (_method: string, params: acp.SessionNotification) => {
        updates.push(params);
      },
    } as unknown as acp.AgentContext;

    await agent.prompt(
      {
        sessionId: session.sessionId,
        prompt: [
          { type: "text", text: "what is in this photo?" },
          { type: "image", data: "AAAA", mimeType: "image/png" },
        ],
      },
      context,
    );

    const text = updates.flatMap((item) => {
      const update = item.update;
      return update.sessionUpdate === "agent_message_chunk" && update.content.type === "text"
        ? [update.content.text]
        : [];
    }).join("");
    expect(text).toContain("attached image (image/png)");

    const echoed = updates.some((item) => {
      const update = item.update;
      return update.sessionUpdate === "agent_message_chunk" &&
        update.content.type === "image" &&
        update.content.data === "AAAA";
    });
    expect(echoed).toBe(true);
  });
});
