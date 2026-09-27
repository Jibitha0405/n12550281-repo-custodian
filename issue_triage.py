from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError


REGION = "ap-southeast-2"
DEFAULT_MODEL_ID = "nvidia.nemotron-super-3-120b"
MAX_ISSUE_BODY_CHARACTERS = 100_000
MAX_SQS_MESSAGE_BYTES = 240 * 1024
PROCESSING_LEASE = timedelta(minutes=15)
DAILY_DIGEST_MODEL_ID = DEFAULT_MODEL_ID
DIGEST_WINDOW = timedelta(hours=24)
DIGEST_ISSUE_LIMIT = 30
MAX_DIGEST_CHARACTERS = 4000
LOCAL_TIMEZONE = ZoneInfo("Australia/Brisbane")
CATEGORIES = {"bug", "feature", "question", "documentation", "other"}
PRIORITIES = {"critical", "high", "medium", "low"}
LOGGER = logging.getLogger(__name__)


class InvalidWebhook(ValueError):
    """The webhook request is invalid or its signature cannot be verified."""


def _header(headers: Any, name: str) -> str | None:
    if not isinstance(headers, dict):
        return None
    return next(
        (value for key, value in headers.items() if isinstance(key, str) and key.lower() == name),
        None,
    )


def _request_body(event: dict[str, Any]) -> bytes:
    body = event.get("body")
    if not isinstance(body, str):
        raise InvalidWebhook("Request body is missing")
    try:
        if event.get("isBase64Encoded") is True:
            return base64.b64decode(body, validate=True)
        return body.encode("utf-8")
    except (UnicodeEncodeError, binascii.Error, ValueError) as error:
        raise InvalidWebhook("Request body encoding is invalid") from error


def verify_github_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify GitHub's SHA-256 HMAC without exposing the configured secret."""
    if not isinstance(signature, str) or not signature.startswith("sha256="):
        return False
    supplied_digest = signature.removeprefix("sha256=")
    if len(supplied_digest) != hashlib.sha256().digest_size * 2:
        return False
    expected_digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_digest, supplied_digest)


def _github_webhook_secret() -> str:
    secret_arn = os.environ.get("WEBHOOK_SECRET_ARN")
    if not secret_arn:
        raise RuntimeError("WEBHOOK_SECRET_ARN must identify the GitHub webhook HMAC secret")
    response = boto3.client("secretsmanager", region_name=REGION).get_secret_value(
        SecretId=secret_arn
    )
    secret = response.get("SecretString")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("The GitHub webhook secret must be stored as a non-empty SecretString")
    return secret


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, separators=(",", ":")),
    }


def _issue_message(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidWebhook("Webhook payload must be a JSON object")
    issue = payload.get("issue")
    repository = payload.get("repository")
    if not isinstance(issue, dict) or not isinstance(repository, dict):
        raise InvalidWebhook("Webhook payload is missing issue or repository details")
    number = issue.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise InvalidWebhook("Issue number must be a positive integer")
    title = issue.get("title")
    if not isinstance(title, str) or not title.strip():
        raise InvalidWebhook("Issue title must be a non-empty string")
    body = issue.get("body", "")
    if body is None:
        body = ""
    if not isinstance(body, str):
        raise InvalidWebhook("Issue body must be a string or null")
    if len(body) > MAX_ISSUE_BODY_CHARACTERS:
        raise InvalidWebhook("Issue body exceeds the supported size")
    repository_name = repository.get("full_name")
    issue_url = issue.get("html_url")
    if not isinstance(repository_name, str) or not repository_name.strip():
        raise InvalidWebhook("Repository full_name is missing")
    if not isinstance(issue_url, str) or not issue_url.startswith("https://"):
        raise InvalidWebhook("Issue URL is missing or invalid")

    return {
        "issueNumber": number,
        "repoFullName": repository_name,
        "issueTitle": title.strip(),
        "issueBody": body,
        "issueUrl": issue_url,
        "receivedAt": datetime.now(timezone.utc).isoformat(),
    }


def webhook_handler(
    event: dict[str, Any],
    context: Any = None,
    *,
    queue_client: Any = None,
    webhook_secret: str | None = None,
) -> dict[str, Any]:
    """Verify an API Gateway GitHub webhook and enqueue opened issues."""
    del context
    headers = event.get("headers")
    event_name = _header(headers, "x-github-event")
    if event_name != "issues":
        return _response(202, {"status": "ignored", "reason": "unsupported event"})

    try:
        body = _request_body(event)
    except InvalidWebhook as error:
        return _response(400, {"error": str(error)})

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _response(400, {"error": "Request body must be valid JSON"})
    if not isinstance(payload, dict):
        return _response(400, {"error": "Webhook payload must be a JSON object"})
    if payload.get("action") != "opened":
        return _response(202, {"status": "ignored", "reason": "unsupported issue action"})

    secret = webhook_secret if webhook_secret is not None else _github_webhook_secret()
    signature = _header(headers, "x-hub-signature-256")
    if not verify_github_signature(body, signature, secret):
        return _response(401, {"error": "Invalid webhook signature"})

    try:
        message = _issue_message(payload)
    except InvalidWebhook as error:
        return _response(400, {"error": str(error)})
    message_body = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    if len(message_body.encode("utf-8")) > MAX_SQS_MESSAGE_BYTES:
        return _response(413, {"error": "Issue payload exceeds the supported SQS message size"})

    queue_url = os.environ.get("TRIAGE_QUEUE_URL")
    if not queue_url:
        raise RuntimeError("TRIAGE_QUEUE_URL must identify the issue triage SQS queue")
    client = queue_client or boto3.client("sqs", region_name=REGION)
    response = client.send_message(
        QueueUrl=queue_url,
        MessageBody=message_body,
    )
    return _response(202, {"status": "queued", "messageId": response["MessageId"]})


def _parse_classification(text: str) -> dict[str, str]:
    decoder = json.JSONDecoder()
    start = text.find("{")
    if start < 0:
        raise ValueError("Bedrock response did not contain a JSON classification")
    try:
        result, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as error:
        raise ValueError("Bedrock response contained invalid classification JSON") from error
    if not isinstance(result, dict):
        raise ValueError("Bedrock classification must be a JSON object")

    category = result.get("category")
    priority = result.get("priority")
    summary = result.get("summary")
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError(f"Bedrock returned unsupported issue category: {category!r}")
    if not isinstance(priority, str) or priority not in PRIORITIES:
        raise ValueError(f"Bedrock returned unsupported issue priority: {priority!r}")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1000:
        raise ValueError("Bedrock returned an invalid issue summary")
    return {"category": category, "priority": priority, "summary": summary.strip()}


def _bedrock_classification(issue: dict[str, Any], client: Any) -> dict[str, str]:
    prompt = {
        "repository": issue["repoFullName"],
        "title": issue["issueTitle"],
        "body": issue["issueBody"],
    }
    response = client.converse(
        modelId=os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
        system=[
            {
                "text": (
                    "Classify the GitHub issue using only the provided issue text. "
                    "Choose category from bug, feature, question, documentation, other. "
                    "Choose priority from critical, high, medium, low. "
                    "Return exactly one JSON object with string fields category, priority, summary."
                )
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [{"text": json.dumps(prompt, ensure_ascii=False)}],
            }
        ],
        inferenceConfig={"maxTokens": 400, "temperature": 0.1},
    )
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    text = "\n".join(
        block["text"] for block in blocks if isinstance(block, dict) and isinstance(block.get("text"), str)
    )
    if not text:
        raise ValueError("Bedrock returned no text for issue classification")
    return _parse_classification(text)


def _is_conditional_failure(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _claim_issue(table: Any, issue: dict[str, Any], now: datetime) -> bool:
    updated_at = now.isoformat()
    lease_expires_before = (now - PROCESSING_LEASE).isoformat()
    try:
        table.update_item(
            Key={"issueNumber": issue["issueNumber"]},
            UpdateExpression=(
                "SET #status = :processing, updatedAt = :updatedAt, "
                "repoFullName = :repo, issueUrl = :url"
            ),
            ConditionExpression=(
                "attribute_not_exists(issueNumber) OR #status = :failed OR "
                "(#status = :processing AND updatedAt < :leaseExpiresBefore)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":processing": "PROCESSING",
                ":failed": "FAILED",
                ":updatedAt": updated_at,
                ":repo": issue["repoFullName"],
                ":url": issue["issueUrl"],
                ":leaseExpiresBefore": lease_expires_before,
            },
        )
        return True
    except ClientError as error:
        if _is_conditional_failure(error):
            return False
        raise


def _save_classification(table: Any, issue: dict[str, Any], result: dict[str, str]) -> None:
    table.update_item(
        Key={"issueNumber": issue["issueNumber"]},
        UpdateExpression=(
            "SET #status = :completed, category = :category, priority = :priority, "
            "summary = :summary, updatedAt = :updatedAt"
        ),
        ConditionExpression="#status = :processing",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":completed": "COMPLETED",
            ":processing": "PROCESSING",
            ":category": result["category"],
            ":priority": result["priority"],
            ":summary": result["summary"],
            ":updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )


def _mark_failed(table: Any, issue_number: int) -> None:
    table.update_item(
        Key={"issueNumber": issue_number},
        UpdateExpression="SET #status = :failed, updatedAt = :updatedAt",
        ConditionExpression="#status = :processing",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":failed": "FAILED",
            ":processing": "PROCESSING",
            ":updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )


def process_issue(
    issue: dict[str, Any],
    *,
    bedrock_client: Any = None,
    issue_table: Any = None,
) -> bool:
    """Claim and classify one queued issue; return False for duplicate in-flight/completed work."""
    if bedrock_client is None:
        bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)
    if issue_table is None:
        table_name = os.environ.get("ISSUE_TABLE_NAME")
        if not table_name:
            raise RuntimeError("ISSUE_TABLE_NAME must identify the issue-triage DynamoDB table")
        issue_table = boto3.resource("dynamodb", region_name=REGION).Table(table_name)

    required = ("issueNumber", "repoFullName", "issueTitle", "issueBody", "issueUrl")
    if any(key not in issue for key in required):
        raise ValueError("Queued issue is missing required fields")
    issue_number = issue["issueNumber"]
    if isinstance(issue_number, bool) or not isinstance(issue_number, int) or issue_number < 1:
        raise ValueError("Queued issue number must be a positive integer")
    if any(not isinstance(issue[key], str) for key in required[1:]):
        raise ValueError("Queued issue text fields must be strings")

    now = datetime.now(timezone.utc)
    if not _claim_issue(issue_table, issue, now):
        LOGGER.info("Skipping duplicate issue %s", issue_number)
        return False

    try:
        classification = _bedrock_classification(issue, bedrock_client)
        _save_classification(issue_table, issue, classification)
    except Exception:
        LOGGER.exception("Issue triage failed for issue %s", issue_number)
        _mark_failed(issue_table, issue_number)
        raise
    return True


def triage_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Process SQS issue records with partial batch failure reporting enabled."""
    del context
    failures: list[dict[str, str]] = []
    for record in event.get("Records", []):
        message_id = record.get("messageId")
        try:
            issue = json.loads(record["body"])
            if not isinstance(issue, dict):
                raise ValueError("SQS issue message must contain a JSON object")
            process_issue(issue)
        except Exception:
            LOGGER.exception("Failed to process SQS message %s", message_id)
            if isinstance(message_id, str) and message_id:
                failures.append({"itemIdentifier": message_id})
            else:
                raise
    return {"batchItemFailures": failures}


def _recent_completed_issues(issue_table: Any, since: datetime) -> list[dict[str, Any]]:
    """Read a bounded set of completed issues updated during the digest window."""
    records: list[dict[str, Any]] = []
    last_evaluated_key: dict[str, Any] | None = None
    while len(records) < DIGEST_ISSUE_LIMIT:
        request: dict[str, Any] = {
            "FilterExpression": "#status = :completed AND updatedAt >= :since",
            "ProjectionExpression": (
                "issueNumber, repoFullName, issueUrl, category, priority, summary, updatedAt"
            ),
            "ExpressionAttributeNames": {"#status": "status"},
            "ExpressionAttributeValues": {
                ":completed": "COMPLETED",
                ":since": since.isoformat(),
            },
            "Limit": DIGEST_ISSUE_LIMIT - len(records),
        }
        if last_evaluated_key:
            request["ExclusiveStartKey"] = last_evaluated_key
        response = issue_table.scan(**request)
        for item in response.get("Items", []):
            records.append(
                {
                    "issueNumber": item["issueNumber"],
                    "repoFullName": item["repoFullName"],
                    "issueUrl": item["issueUrl"],
                    "category": item["category"],
                    "priority": item["priority"],
                    "summary": item["summary"][:500],
                    "updatedAt": item["updatedAt"],
                }
            )
            if len(records) >= DIGEST_ISSUE_LIMIT:
                break
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
    return records


def _daily_digest_text(issues: list[dict[str, Any]], client: Any) -> str:
    model_id = os.environ.get("BEDROCK_MODEL_ID", DAILY_DIGEST_MODEL_ID)
    response = client.converse(
        modelId=model_id,
        system=[
            {
                "text": (
                    "Write a concise daily repository issue digest using only the supplied "
                    "completed issue records. Summarize repeated themes, notable priorities, "
                    "and actionable patterns. Do not infer facts that are not in the records. "
                    "If the list is empty, clearly state that no issues were completed in the "
                    "period. Keep the response under 400 words."
                )
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": json.dumps(
                            {"completedIssues": issues},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    }
                ],
            }
        ],
        inferenceConfig={"maxTokens": 700, "temperature": 0.2},
    )
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    text = "\n".join(
        block["text"] for block in blocks if isinstance(block, dict) and isinstance(block.get("text"), str)
    ).strip()
    if not text:
        raise ValueError("Bedrock returned no text for the daily digest")
    if len(text) > MAX_DIGEST_CHARACTERS:
        raise ValueError("Bedrock daily digest exceeded the supported length")
    return text


def generate_daily_digest(
    *,
    bedrock_client: Any = None,
    issue_table: Any = None,
    run_table: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Summarize the last 24 hours of completed issues and persist one record per Brisbane day."""
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("Digest generation time must include a timezone")
    current_time = current_time.astimezone(timezone.utc)

    if issue_table is None:
        issue_table_name = os.environ.get("ISSUE_TABLE_NAME")
        if not issue_table_name:
            raise RuntimeError("ISSUE_TABLE_NAME must identify the issue-triage DynamoDB table")
        issue_table = boto3.resource("dynamodb", region_name=REGION).Table(issue_table_name)
    if run_table is None:
        run_table_name = os.environ.get("DIGEST_TABLE_NAME")
        if not run_table_name:
            raise RuntimeError("DIGEST_TABLE_NAME must identify the daily-digest DynamoDB table")
        run_table = boto3.resource("dynamodb", region_name=REGION).Table(run_table_name)
    if bedrock_client is None:
        bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)

    window_start = current_time - DIGEST_WINDOW
    issues = _recent_completed_issues(issue_table, window_start)
    digest = _daily_digest_text(issues, bedrock_client)
    local_date = current_time.astimezone(LOCAL_TIMEZONE).date().isoformat()
    run_id = f"daily-digest#{local_date}"
    item = {
        "runId": run_id,
        "runType": "daily-digest",
        "status": "COMPLETED",
        "digest": digest,
        "issueCount": len(issues),
        "issueReferences": [
            {
                "issueNumber": issue["issueNumber"],
                "repoFullName": issue["repoFullName"],
                "issueUrl": issue["issueUrl"],
                "category": issue["category"],
                "priority": issue["priority"],
            }
            for issue in issues
        ],
        "windowStart": window_start.isoformat(),
        "generatedAt": current_time.isoformat(),
        "modelId": os.environ.get("BEDROCK_MODEL_ID", DAILY_DIGEST_MODEL_ID),
    }
    try:
        run_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(runId)",
        )
    except ClientError as error:
        if not _is_conditional_failure(error):
            raise
        LOGGER.info("Daily digest already exists for %s", local_date)
        return {"status": "already_exists", "runId": run_id}

    LOGGER.info("Saved daily digest %s for %s completed issues", run_id, len(issues))
    return {"status": "created", "runId": run_id, "issueCount": len(issues)}


def digest_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """EventBridge target for the daily digest schedule."""
    del event, context
    result = generate_daily_digest()
    return {"statusCode": 200, "body": json.dumps(result, separators=(",", ":"))}


__all__ = [
    "digest_handler",
    "generate_daily_digest",
    "InvalidWebhook",
    "process_issue",
    "triage_handler",
    "verify_github_signature",
    "webhook_handler",
]
