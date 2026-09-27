from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError

import issue_triage


WEBHOOK_SECRET = "local-test-secret"
ISSUE = {
    "issueNumber": 17,
    "repoFullName": "student/repository",
    "issueTitle": "Login fails after password reset",
    "issueBody": "The login page returns an error after resetting a password.",
    "issueUrl": "https://github.com/student/repository/issues/17",
}


class FakeQueue:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, **kwargs: str) -> dict[str, str]:
        self.messages.append(kwargs)
        return {"MessageId": "queued-message-id"}


class FakeBedrock:
    def __init__(self, response: str) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def converse(self, **kwargs: object) -> dict[str, object]:
        self.requests.append(kwargs)
        return {
            "output": {
                "message": {
                    "content": [{"text": self.response}],
                }
            }
        }


class FakeIssueTable:
    def __init__(self) -> None:
        self.status: str | None = None
        self.updates: list[dict[str, object]] = []

    def update_item(self, **kwargs: object) -> dict[str, object]:
        self.updates.append(kwargs)
        expression = kwargs["UpdateExpression"]
        values = kwargs["ExpressionAttributeValues"]
        if "category = :category" in expression:
            self.status = values[":completed"]
        elif "SET #status = :failed" in expression:
            self.status = values[":failed"]
        else:
            condition = kwargs["ConditionExpression"]
            if self.status is not None and "attribute_not_exists(issueNumber)" in condition:
                raise ClientError(
                    {
                        "Error": {
                            "Code": "ConditionalCheckFailedException",
                            "Message": "Already claimed",
                        }
                    },
                    "UpdateItem",
                )
            self.status = values[":processing"]
        return {}


class FakeDigestIssueTable:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self.items = items
        self.scans: list[dict[str, object]] = []

    def scan(self, **kwargs: object) -> dict[str, object]:
        self.scans.append(kwargs)
        return {"Items": self.items}


class FakeDigestRunTable:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {}
        self.puts: list[dict[str, object]] = []

    def put_item(self, **kwargs: object) -> dict[str, object]:
        self.puts.append(kwargs)
        item = kwargs["Item"]
        run_id = item["runId"]
        if run_id in self.items:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ConditionalCheckFailedException",
                        "Message": "Digest already exists",
                    }
                },
                "PutItem",
            )
        self.items[run_id] = item
        return {}


def signed_event(payload: dict[str, object], *, action: str = "opened") -> dict[str, object]:
    body = json.dumps({"action": action, **payload}, separators=(",", ":"))
    digest = hmac.new(WEBHOOK_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return {
        "headers": {
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": f"sha256={digest}",
        },
        "body": body,
        "isBase64Encoded": False,
    }


def github_payload() -> dict[str, object]:
    return {
        "issue": {
            "number": ISSUE["issueNumber"],
            "title": ISSUE["issueTitle"],
            "body": ISSUE["issueBody"],
            "html_url": ISSUE["issueUrl"],
        },
        "repository": {"full_name": ISSUE["repoFullName"]},
    }


class SignatureTests(unittest.TestCase):
    def test_accepts_valid_sha256_signature_and_rejects_altered_body(self) -> None:
        body = b'{"action":"opened"}'
        signature = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(issue_triage.verify_github_signature(body, signature, WEBHOOK_SECRET))
        self.assertFalse(issue_triage.verify_github_signature(body + b" ", signature, WEBHOOK_SECRET))
        self.assertFalse(issue_triage.verify_github_signature(body, "sha1=bad", WEBHOOK_SECRET))
        self.assertFalse(issue_triage.verify_github_signature(body, 123, WEBHOOK_SECRET))  # type: ignore[arg-type]


class WebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = FakeQueue()

    def test_valid_issue_opened_event_is_enqueued(self) -> None:
        with patch.dict("os.environ", {"TRIAGE_QUEUE_URL": "https://sqs.local/triage"}):
            result = issue_triage.webhook_handler(
                signed_event(github_payload()),
                queue_client=self.queue,
                webhook_secret=WEBHOOK_SECRET,
            )

        self.assertEqual(result["statusCode"], 202)
        self.assertEqual(json.loads(result["body"])["messageId"], "queued-message-id")
        self.assertEqual(len(self.queue.messages), 1)
        message = json.loads(self.queue.messages[0]["MessageBody"])
        self.assertEqual(message["issueNumber"], ISSUE["issueNumber"])
        self.assertEqual(message["repoFullName"], ISSUE["repoFullName"])

    def test_rejects_invalid_signature_without_enqueuing(self) -> None:
        event = signed_event(github_payload())
        event["headers"]["X-Hub-Signature-256"] = "sha256=" + "0" * 64  # type: ignore[index]
        response = issue_triage.webhook_handler(
            event,
            queue_client=self.queue,
            webhook_secret=WEBHOOK_SECRET,
        )
        self.assertEqual(response["statusCode"], 401)
        self.assertEqual(self.queue.messages, [])

    def test_ignores_non_open_actions_without_fetching_secret(self) -> None:
        event = signed_event(github_payload(), action="edited")
        with patch.object(issue_triage, "_github_webhook_secret", side_effect=AssertionError):
            response = issue_triage.webhook_handler(event, queue_client=self.queue)
        self.assertEqual(response["statusCode"], 202)
        self.assertEqual(self.queue.messages, [])

    def test_returns_bad_request_for_invalid_issue_payload(self) -> None:
        payload = github_payload()
        payload["issue"]["number"] = -1  # type: ignore[index]
        response = issue_triage.webhook_handler(
            signed_event(payload),
            queue_client=self.queue,
            webhook_secret=WEBHOOK_SECRET,
        )
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(self.queue.messages, [])

    def test_rejects_issue_payload_that_would_exceed_sqs_message_limit(self) -> None:
        payload = github_payload()
        payload["issue"]["body"] = "\x00" * 50_000  # type: ignore[index]
        response = issue_triage.webhook_handler(
            signed_event(payload),
            queue_client=self.queue,
            webhook_secret=WEBHOOK_SECRET,
        )
        self.assertEqual(response["statusCode"], 413)
        self.assertEqual(self.queue.messages, [])


class TriageTests(unittest.TestCase):
    def test_classifies_and_persists_issue(self) -> None:
        bedrock = FakeBedrock(
            '{"category":"bug","priority":"high","summary":"Password reset leaves login unusable."}'
        )
        table = FakeIssueTable()
        processed = issue_triage.process_issue(
            ISSUE,
            bedrock_client=bedrock,
            issue_table=table,
        )
        self.assertTrue(processed)
        self.assertEqual(table.status, "COMPLETED")
        self.assertEqual(len(bedrock.requests), 1)
        self.assertEqual(bedrock.requests[0]["modelId"], issue_triage.DEFAULT_MODEL_ID)
        self.assertEqual(len(table.updates), 2)

    def test_duplicate_issue_is_not_sent_to_bedrock_twice(self) -> None:
        bedrock = FakeBedrock('{"category":"bug","priority":"low","summary":"Duplicate."}')
        table = FakeIssueTable()
        table.status = "COMPLETED"
        self.assertFalse(
            issue_triage.process_issue(ISSUE, bedrock_client=bedrock, issue_table=table)
        )
        self.assertEqual(bedrock.requests, [])

    def test_rejects_invalid_model_classification_and_marks_issue_failed(self) -> None:
        bedrock = FakeBedrock('{"category":"unknown","priority":"high","summary":"Invalid."}')
        table = FakeIssueTable()
        with self.assertLogs("issue_triage", level="ERROR"):
            with self.assertRaisesRegex(ValueError, "unsupported issue category"):
                issue_triage.process_issue(ISSUE, bedrock_client=bedrock, issue_table=table)
        self.assertEqual(table.status, "FAILED")

    def test_reports_only_failed_sqs_message_ids(self) -> None:
        event = {
            "Records": [
                {"messageId": "ok", "body": json.dumps(ISSUE)},
                {"messageId": "bad", "body": "not-json"},
            ]
        }
        with self.assertLogs("issue_triage", level="ERROR"):
            with patch.object(issue_triage, "process_issue", side_effect=[True, ValueError("bad")]):
                result = issue_triage.triage_handler(event)
        self.assertEqual(result, {"batchItemFailures": [{"itemIdentifier": "bad"}]})


class DailyDigestTests(unittest.TestCase):
    def test_generates_and_persists_digest_for_recent_completed_issues(self) -> None:
        issue = {
            "issueNumber": 17,
            "repoFullName": "student/repository",
            "issueUrl": "https://github.com/student/repository/issues/17",
            "category": "bug",
            "priority": "high",
            "summary": "Password reset leaves login unusable.",
            "updatedAt": "2026-09-27T08:00:00+00:00",
        }
        issues = FakeDigestIssueTable([issue])
        runs = FakeDigestRunTable()
        bedrock = FakeBedrock("One high-priority bug was completed around password reset.")
        fixed_now = issue_triage.datetime(2026, 9, 27, 9, 0, tzinfo=issue_triage.timezone.utc)

        result = issue_triage.generate_daily_digest(
            bedrock_client=bedrock,
            issue_table=issues,
            run_table=runs,
            now=fixed_now,
        )

        self.assertEqual(result, {"status": "created", "runId": "daily-digest#2026-09-27", "issueCount": 1})
        self.assertEqual(len(issues.scans), 1)
        self.assertIn("updatedAt >= :since", issues.scans[0]["FilterExpression"])
        self.assertEqual(issues.scans[0]["ExpressionAttributeValues"][":completed"], "COMPLETED")
        saved = runs.items["daily-digest#2026-09-27"]
        self.assertEqual(saved["status"], "COMPLETED")
        self.assertEqual(saved["issueCount"], 1)
        self.assertEqual(saved["digest"], bedrock.response)
        self.assertEqual(saved["issueReferences"][0]["issueNumber"], 17)
        self.assertEqual(bedrock.requests[0]["modelId"], issue_triage.DEFAULT_MODEL_ID)

    def test_creates_a_no_issues_digest_and_duplicate_run_is_idempotent(self) -> None:
        issues = FakeDigestIssueTable([])
        runs = FakeDigestRunTable()
        bedrock = FakeBedrock("No issues were completed during the last 24 hours.")
        fixed_now = issue_triage.datetime(2026, 9, 27, 9, 0, tzinfo=issue_triage.timezone.utc)

        created = issue_triage.generate_daily_digest(
            bedrock_client=bedrock,
            issue_table=issues,
            run_table=runs,
            now=fixed_now,
        )
        duplicate = issue_triage.generate_daily_digest(
            bedrock_client=bedrock,
            issue_table=issues,
            run_table=runs,
            now=fixed_now,
        )

        self.assertEqual(created["issueCount"], 0)
        self.assertEqual(duplicate, {"status": "already_exists", "runId": "daily-digest#2026-09-27"})
        self.assertEqual(runs.items["daily-digest#2026-09-27"]["issueReferences"], [])

    def test_requires_timezone_aware_digest_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "must include a timezone"):
            issue_triage.generate_daily_digest(
                bedrock_client=FakeBedrock("Digest"),
                issue_table=FakeDigestIssueTable([]),
                run_table=FakeDigestRunTable(),
                now=issue_triage.datetime(2026, 9, 27, 9, 0),
            )


if __name__ == "__main__":
    unittest.main()
