"""Tests for the parallel rate-limit coordinator used by the images skill.

Covers _ParallelRateLimitCoordinator, which closes the technical debt
called out in CLAUDE.md § Known design debt: "images parallel path still
lacks coordinated backoff". The sequential path (generate_and_upload_batch
→ _generate_with_batch_backoff) already handled this since v1.4.3; the
parallel path now matches via this coordinator.

We pin jitter_max=0.0 in tests for deterministic timing.
"""

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_and_upload_images import _ParallelRateLimitCoordinator


class CoordinatorTests(TestCase):
    def test_no_pause_on_init(self):
        coord = _ParallelRateLimitCoordinator(delays=(1,), jitter_max=0.0)
        self.assertFalse(coord.is_paused())

    def test_signal_returns_zero_when_attempt_exceeds_schedule(self):
        coord = _ParallelRateLimitCoordinator(delays=(0.1, 0.2), jitter_max=0.0)
        self.assertGreater(coord.signal_rate_limit(0), 0)
        self.assertGreater(coord.signal_rate_limit(1), 0)
        self.assertEqual(coord.signal_rate_limit(2), 0.0)
        self.assertEqual(coord.signal_rate_limit(99), 0.0)

    def test_signal_uses_scheduled_delay_with_no_jitter(self):
        coord = _ParallelRateLimitCoordinator(delays=(0.5,), jitter_max=0.0)
        self.assertAlmostEqual(coord.signal_rate_limit(0), 0.5, places=2)

    def test_concurrent_signals_coalesce_to_longest_window(self):
        # delays[1]=1.0 > delays[0]=0.1, so signaling 1 then 0 should NOT
        # shrink the pause window — only longer end-times persist.
        coord = _ParallelRateLimitCoordinator(delays=(0.1, 1.0), jitter_max=0.0)
        coord.signal_rate_limit(1)
        with coord._lock:
            longer_end = coord._pause_until
        coord.signal_rate_limit(0)
        with coord._lock:
            after_short_signal = coord._pause_until
        self.assertEqual(longer_end, after_short_signal)

    def test_wait_returns_immediately_when_no_active_pause(self):
        coord = _ParallelRateLimitCoordinator(delays=(1,), jitter_max=0.0)
        start = time.time()
        coord.wait_if_paused()
        self.assertLess(time.time() - start, 0.05)

    def test_wait_blocks_for_pause_duration(self):
        coord = _ParallelRateLimitCoordinator(delays=(0.3,), jitter_max=0.0)
        coord.signal_rate_limit(0)
        start = time.time()
        coord.wait_if_paused()
        elapsed = time.time() - start
        # Allow some slop above the polling granularity (1s), below for jitter
        self.assertGreaterEqual(elapsed, 0.25)
        self.assertLess(elapsed, 1.5)

    def test_wait_unblocks_after_pause_expires(self):
        coord = _ParallelRateLimitCoordinator(delays=(0.2,), jitter_max=0.0)
        coord.signal_rate_limit(0)
        time.sleep(0.3)
        start = time.time()
        coord.wait_if_paused()
        self.assertLess(time.time() - start, 0.05)

    def test_concurrent_workers_all_block_during_pause(self):
        """Multiple workers calling wait_if_paused before/during a pause window
        must all unblock together when the window expires, not race past it."""
        coord = _ParallelRateLimitCoordinator(delays=(0.4,), jitter_max=0.0)
        coord.signal_rate_limit(0)

        unblock_times: list[float] = []
        unblock_lock = threading.Lock()

        def worker():
            coord.wait_if_paused()
            with unblock_lock:
                unblock_times.append(time.time())

        signal_time = time.time()
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(worker) for _ in range(4)]
            for f in futures:
                f.result()

        self.assertEqual(len(unblock_times), 4)
        for t in unblock_times:
            # All workers should have waited at least ~0.4s minus a small slop
            self.assertGreaterEqual(t - signal_time, 0.35)

    def test_signal_during_active_pause_extends_to_longer_end(self):
        """Worker B hitting a longer-wave 429 while worker A's shorter
        pause is still active should EXTEND the window, not reset it short."""
        coord = _ParallelRateLimitCoordinator(delays=(0.2, 1.0), jitter_max=0.0)
        coord.signal_rate_limit(0)
        time.sleep(0.05)
        coord.signal_rate_limit(1)
        with coord._lock:
            remaining = coord._pause_until - time.time()
        # Should be very close to the larger delay (1.0s), minus the 0.05s elapsed.
        self.assertGreater(remaining, 0.85)

    def test_signal_with_smaller_attempt_does_not_shrink_active_pause(self):
        coord = _ParallelRateLimitCoordinator(delays=(0.1, 1.0), jitter_max=0.0)
        coord.signal_rate_limit(1)  # set ~1.0s pause
        with coord._lock:
            before = coord._pause_until
        coord.signal_rate_limit(0)  # would only request 0.1s — should not shrink
        with coord._lock:
            after = coord._pause_until
        self.assertEqual(before, after)

    def test_jitter_stays_within_bound(self):
        coord = _ParallelRateLimitCoordinator(delays=(1.0,), jitter_max=2.0)
        delay = coord.signal_rate_limit(0)
        self.assertGreaterEqual(delay, 1.0)
        self.assertLessEqual(delay, 3.0)


class ParallelRetryIntegrationTests(TestCase):
    """End-to-end checks that generate_and_upload_parallel actually wires
    RateLimitExhausted through the coordinator and retries / gives up correctly.
    """

    def _patch_module(self, monkey: dict):
        import scripts.generate_and_upload_images as mod
        originals = {k: getattr(mod, k) for k in monkey}
        for k, v in monkey.items():
            setattr(mod, k, v)
        return mod, originals

    def _restore(self, mod, originals):
        for k, v in originals.items():
            setattr(mod, k, v)

    def test_worker_retries_after_rate_limit_then_succeeds(self):
        import scripts.generate_and_upload_images as mod

        call_counts: dict[str, int] = {}
        call_lock = threading.Lock()

        def fake_generate(config, resolution, model):
            with call_lock:
                n = call_counts.get(config.name, 0) + 1
                call_counts[config.name] = n
            if n == 1:
                raise mod.RateLimitExhausted("test 429 wave 1", ["gemini-3-pro-image-preview"])
            config.local_path = f"/tmp/{config.filename}"
            return True

        mod_ref, originals = self._patch_module({
            "BATCH_BACKOFF_DELAYS_SEC": (0.1,),
            "BATCH_BACKOFF_JITTER_MAX_SEC": 0.0,
            "generate_image": fake_generate,
        })
        try:
            configs = [
                mod_ref.ImageConfig(name=f"img{i}", prompt="x", aspect_ratio="16:9")
                for i in range(3)
            ]
            results = mod_ref.generate_and_upload_parallel(
                configs, upload=False, max_workers=2, fail_fast=False
            )
            self.assertEqual(results["generated"], 3)
            self.assertEqual(results["failed"], 0)
            for c in configs:
                self.assertEqual(call_counts[c.name], 2)  # one retry each
        finally:
            self._restore(mod_ref, originals)

    def test_worker_gives_up_after_exhausting_batch_backoff(self):
        import scripts.generate_and_upload_images as mod

        def fake_generate(config, resolution, model):
            raise mod.RateLimitExhausted("permanent 429", ["gemini-3-pro-image-preview"])

        mod_ref, originals = self._patch_module({
            "BATCH_BACKOFF_DELAYS_SEC": (0.05, 0.05),  # 2 waves, very short
            "BATCH_BACKOFF_JITTER_MAX_SEC": 0.0,
            "generate_image": fake_generate,
        })
        try:
            configs = [mod_ref.ImageConfig(name="img0", prompt="x", aspect_ratio="16:9")]
            results = mod_ref.generate_and_upload_parallel(
                configs, upload=False, max_workers=1, fail_fast=False
            )
            self.assertEqual(results["generated"], 0)
            self.assertEqual(results["failed"], 1)
            self.assertEqual(len(results["errors"]), 1)
            err = results["errors"][0]
            self.assertEqual(err["type"], "RateLimitExhausted")
            self.assertIn("批量级退避已用尽", err["error"])
        finally:
            self._restore(mod_ref, originals)


if __name__ == "__main__":
    main()
