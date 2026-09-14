import argparse
import copy
import tempfile
import unittest
from unittest.mock import patch

import wake


def limits(primary=20, secondary=30):
    return {"rateLimitsByLimitId": {"codex": {
        "primary": {"usedPercent": primary, "resetsAt": 100},
        "secondary": {"usedPercent": secondary, "resetsAt": 200}}}}


class QuotaTests(unittest.TestCase):
    def test_both_windows_must_be_available(self):
        self.assertEqual(wake.quota_state(limits(10, 100)), ("blocked", 200))
        self.assertEqual(wake.quota_state(limits(100, 100)), ("blocked", 200))
        self.assertEqual(wake.quota_state(limits()), ("available", None))

    def test_unknown_never_resumes(self):
        for data in ({}, {"rateLimits": {}}, limits(None), limits(float("nan")), limits(True)):
            self.assertEqual(wake.quota_state(data)[0], "unknown")

    def test_multi_bucket_wins_over_legacy(self):
        data = limits(100)
        data["rateLimits"] = {"primary": {"usedPercent": 0}}
        self.assertEqual(wake.quota_state(data)[0], "blocked")
        self.assertEqual(wake.quota_state(data, "missing")[0], "unknown")

    def test_old_timestamp_does_not_mean_capacity(self):
        self.assertEqual(wake.quota_state(limits(100))[0], "blocked")

    def test_only_structured_usage_error(self):
        for status in ("completed", "interrupted", "inProgress"):
            self.assertFalse(wake.usage_failure({"status": status, "error": {"codexErrorInfo": "usageLimitExceeded"}}))
        self.assertFalse(wake.usage_failure({"status": "failed", "error": {"message": "usage limit"}}))


FAILED = {"id": "t1", "status": "failed", "error": {"codexErrorInfo": "usageLimitExceeded"}}


class FakeClient:
    def __init__(self):
        self.calls = []
        self.thread = {"id": "thread1", "status": {"type": "idle"}, "turns": [copy.deepcopy(FAILED)]}
        self.capacities = [limits(100), limits()]

    def call(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        if method == "thread/read" or method == "thread/resume":
            return {"thread": copy.deepcopy(self.thread)}
        if method == "account/rateLimits/read":
            return self.capacities.pop(0) if len(self.capacities) > 1 else self.capacities[0]
        if method == "turn/start":
            return {"turn": {"id": "t2", "status": "inProgress"}}
        if method == "turn/interrupt":
            return {}
        raise AssertionError(method)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.journal = wake.Journal(self.temp.name)
        self.args = argparse.Namespace(command="resume", thread="thread1", max_resumes=3,
            bucket="codex", poll=15, max_wait=120)
        self.client = FakeClient()

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def test_reset_then_exact_thread_resume(self):
        with patch("wake.wait_for_capacity", side_effect=lambda *a: wake.wait_for_capacity_original(*a, sleep=lambda _: None)), \
             patch("wake.wait_for_turn", return_value={"id": "t2", "status": "completed"}):
            wake.run(self.args, self.client, self.journal, lambda _: None)
        starts = [p for m, p in self.client.calls if m == "turn/start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]["threadId"], "thread1")
        self.assertNotIn("approvalPolicy", starts[0])

    def test_completed_and_cancelled_tasks_do_not_restart(self):
        for status in ("completed", "interrupted"):
            self.client.thread["turns"][-1]["status"] = status
            with self.assertRaises(wake.WakeError):
                wake.run(self.args, self.client, self.journal)
        self.assertFalse(any(m == "turn/start" for m, _ in self.client.calls))

    def test_changed_task_is_not_resumed(self):
        def change(*args):
            self.client.thread["turns"][-1]["id"] = "someone-else"
        with patch("wake.wait_for_capacity", side_effect=change):
            with self.assertRaises(wake.WakeError):
                wake.run(self.args, self.client, self.journal)
        self.assertFalse(any(m == "turn/start" for m, _ in self.client.calls))

    def test_uncertain_dispatch_is_not_repeated(self):
        self.journal.claim("thread1", "t1")
        with self.assertRaises(wake.WakeError):
            self.journal.claim("thread1", "t1")
        self.journal.close()
        self.journal = wake.Journal(self.temp.name)
        with self.assertRaises(wake.WakeError):
            self.journal.claim("thread1", "t1")

    def test_second_watcher_is_blocked(self):
        with self.assertRaises(wake.WakeError):
            wake.Journal(self.temp.name)

    def test_interrupt_on_keyboard_cancel(self):
        with patch("wake.wait_for_capacity"), patch("wake.wait_for_turn", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                wake.run(self.args, self.client, self.journal, lambda _: None)
        self.assertIn(("turn/interrupt", {"threadId": "thread1", "turnId": "t2"}), self.client.calls)


wake.wait_for_capacity_original = wake.wait_for_capacity
if __name__ == "__main__":
    unittest.main()
