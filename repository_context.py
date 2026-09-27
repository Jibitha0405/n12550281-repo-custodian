from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REGION = "ap-southeast-2"
VECTOR_BUCKET = "n12550281-a2-vectors"
VECTOR_INDEX = "repo-context"
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSIONS = 1024
VECTOR_KEY_PREFIX = "repo-custodian/"
CHUNK_CHARACTERS = 1200
VECTOR_BATCH_SIZE = 100

SOURCE_FILES = (
    Path("README.md"),
    Path("webui/README.md"),
    Path("CAB432-Strobe-Server-Py-1.0.0/README.md"),
    Path("CAB432-Strobe-Server-Py-1.0.0/insomnia/strobe-openapi.yaml"),
)


@dataclass(frozen=True)
class TextChunk:
    key: str
    source: str
    text: str
    line_start: int
    line_end: int


def iter_chunks(root: Path) -> list[TextChunk]:
    """Read the curated factual project documents and split them into bounded chunks."""
    chunks: list[TextChunk] = []

    for relative_path in SOURCE_FILES:
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Required repository context file is missing: {relative_path}")

        lines = path.read_text(encoding="utf-8").splitlines()
        pending: list[str] = []
        pending_length = 0
        first_line = 1

        def flush(last_line: int) -> None:
            nonlocal pending, pending_length, first_line
            text = "\n".join(pending).strip()
            if text:
                key = f"{VECTOR_KEY_PREFIX}{relative_path.as_posix()}#{len(chunks)}"
                chunks.append(
                    TextChunk(
                        key=key,
                        source=relative_path.as_posix(),
                        text=text,
                        line_start=first_line,
                        line_end=last_line,
                    )
                )
            pending = []
            pending_length = 0

        for line_number, line in enumerate(lines, start=1):
            if len(line) > CHUNK_CHARACTERS:
                flush(line_number - 1)
                for offset in range(0, len(line), CHUNK_CHARACTERS):
                    piece = line[offset : offset + CHUNK_CHARACTERS]
                    key = f"{VECTOR_KEY_PREFIX}{relative_path.as_posix()}#{len(chunks)}"
                    chunks.append(
                        TextChunk(
                            key=key,
                            source=relative_path.as_posix(),
                            text=piece,
                            line_start=line_number,
                            line_end=line_number,
                        )
                    )
                first_line = line_number + 1
                continue

            added_length = len(line) + (1 if pending else 0)
            if pending and pending_length + added_length > CHUNK_CHARACTERS:
                flush(line_number - 1)
                first_line = line_number

            if not pending:
                first_line = line_number
            pending.append(line)
            pending_length += len(line) + (1 if len(pending) > 1 else 0)

        flush(len(lines))

    return chunks


def embed_text(client: Any, text: str) -> list[float]:
    response = client.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps(
            {
                "inputText": text,
                "dimensions": EMBEDDING_DIMENSIONS,
                "normalize": True,
            }
        ),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(response["body"].read())
    vector = payload.get("embedding")
    if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Bedrock returned an invalid embedding; expected {EMBEDDING_DIMENSIONS} values"
        )
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector):
        raise ValueError("Bedrock returned an embedding containing invalid numeric values")
    return [float(value) for value in vector]


def _existing_project_keys(vectors_client: Any) -> set[str]:
    keys: set[str] = set()
    next_token: str | None = None
    while True:
        request: dict[str, Any] = {
            "vectorBucketName": VECTOR_BUCKET,
            "indexName": VECTOR_INDEX,
            "maxResults": 500,
        }
        if next_token:
            request["nextToken"] = next_token
        response = vectors_client.list_vectors(**request)
        keys.update(
            vector["key"]
            for vector in response.get("vectors", [])
            if vector["key"].startswith(VECTOR_KEY_PREFIX)
        )
        next_token = response.get("nextToken")
        if not next_token:
            return keys


def _batched(values: list[Any], size: int) -> list[list[Any]]:
    return [values[offset : offset + size] for offset in range(0, len(values), size)]


def index_repository(root: Path, bedrock_client: Any, vectors_client: Any) -> int:
    """Embed curated repository documents and replace this tool's existing vectors."""
    chunks = iter_chunks(root)
    if not chunks:
        raise ValueError("No repository context chunks were found")

    existing_keys = _existing_project_keys(vectors_client)
    vectors: list[dict[str, Any]] = []
    for chunk in chunks:
        vectors.append(
            {
                "key": chunk.key,
                "data": {"float32": embed_text(bedrock_client, chunk.text)},
                "metadata": {
                    "source": chunk.source,
                    "text": chunk.text,
                    "lineStart": chunk.line_start,
                    "lineEnd": chunk.line_end,
                },
            }
        )

    new_keys = {vector["key"] for vector in vectors}
    for batch in _batched(vectors, VECTOR_BATCH_SIZE):
        vectors_client.put_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=VECTOR_INDEX,
            vectors=batch,
        )

    stale_keys = sorted(existing_keys - new_keys)
    for batch in _batched(stale_keys, VECTOR_BATCH_SIZE):
        vectors_client.delete_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=VECTOR_INDEX,
            keys=batch,
        )

    return len(vectors)


def search_repository(
    question: str,
    bedrock_client: Any,
    vectors_client: Any,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return the closest repository chunks, including their source text and line ranges."""
    if not question.strip():
        raise ValueError("Search question must not be empty")
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20")

    response = vectors_client.query_vectors(
        vectorBucketName=VECTOR_BUCKET,
        indexName=VECTOR_INDEX,
        queryVector={"float32": embed_text(bedrock_client, question)},
        topK=top_k,
        returnMetadata=True,
        returnDistance=True,
    )
    return response.get("vectors", [])


def _create_clients() -> tuple[Any, Any]:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required to access Amazon Bedrock and S3 Vectors"
        ) from exc

    return (
        boto3.client("bedrock-runtime", region_name=REGION),
        boto3.client("s3vectors", region_name=REGION),
    )


def run_mcp_server() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("The mcp package is required to run the MCP server") from exc

    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "3001"))
    server = FastMCP(
        "Repository Custodian",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )

    @server.tool()
    def search_repository_context(question: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Find repository documentation relevant to a question; include sources and line ranges."""
        bedrock_client, vectors_client = _create_clients()
        results = search_repository(question, bedrock_client, vectors_client, top_k=top_k)
        return [
            {
                "source": result["metadata"]["source"],
                "line_start": result["metadata"]["lineStart"],
                "line_end": result["metadata"]["lineEnd"],
                "text": result["metadata"]["text"],
                "distance": result.get("distance"),
            }
            for result in results
        ]

    server.run(transport="streamable-http")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index and search repository context.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    index_parser = subparsers.add_parser("index", help="Embed curated repository documents.")
    index_parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    search_parser = subparsers.add_parser("search", help="Search indexed repository context.")
    search_parser.add_argument("question")
    search_parser.add_argument("--top-k", type=int, default=5)
    subparsers.add_parser("serve", help="Run the repository context MCP server.")
    args = parser.parse_args()

    if args.command == "serve":
        run_mcp_server()
        return

    bedrock_client, vectors_client = _create_clients()
    if args.command == "index":
        count = index_repository(args.root.resolve(), bedrock_client, vectors_client)
        print(f"Indexed {count} repository context chunks.")
        return

    results = search_repository(
        args.question,
        bedrock_client,
        vectors_client,
        top_k=args.top_k,
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
