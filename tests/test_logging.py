import json
import logging
import unittest

from apira_logging import JsonFormatter, reset_request_id, set_request_id


class StructuredLoggingTests(unittest.TestCase):
    def test_json_fields_redaction_and_correlation(self):
        request_id = "123e4567-e89b-12d3-a456-426614174000"
        token = set_request_id(request_id)
        try:
            record = logging.LogRecord(
                "apira-rag",
                logging.INFO,
                __file__,
                1,
                "Safe message",
                (),
                None,
            )
            record.event = "test.event"
            record.query = "full private query"
            record.prompt = "full private prompt"
            record.vector = [0.1, 0.2]
            payload = json.loads(JsonFormatter().format(record))
        finally:
            reset_request_id(token)

        self.assertEqual(payload["request_id"], request_id)
        self.assertEqual(payload["query"], "[REDACTED]")
        self.assertEqual(payload["prompt"], "[REDACTED]")
        self.assertEqual(payload["vector"], "[REDACTED]")
        for field in (
            "timestamp",
            "level",
            "service",
            "environment",
            "event",
            "message",
            "request_id",
        ):
            self.assertIn(field, payload)


if __name__ == "__main__":
    unittest.main()
