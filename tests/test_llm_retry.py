"""The retry backoff, which the batch depends on to survive its own concurrency.

25 sessions run against one endpoint at a structural ceiling of 75 in-flight requests.
When that endpoint does push back, it pushes back on many requests at the same instant —
so the property that matters is not the mean wait but that the retries SPREAD.
"""

from __future__ import annotations

from ps1982.llm.base import _is_transient, _jittered


def test_backoff_never_exceeds_the_undithered_window():
    """Jitter may only shorten a wait, never lengthen it past the intended ceiling."""
    for attempt in range(1, 6):
        ceiling = 2.0 ** attempt
        assert all(_jittered(2.0, attempt) <= ceiling for _ in range(2000))


def test_backoff_is_floored_so_a_low_draw_is_not_an_instant_re_hammer():
    assert all(_jittered(2.0, 1) >= 0.5 for _ in range(2000))


def test_backoff_grows_with_the_attempt_number():
    """Successive attempts back off further — the exponential shape must survive jitter."""
    means = [sum(_jittered(2.0, a) for _ in range(4000)) / 4000 for a in range(1, 6)]
    assert means == sorted(means)
    # each window doubles, so each mean should roughly double once clear of the floor
    for lo, hi in zip(means[1:], means[2:]):
        assert 1.7 < hi / lo < 2.3


def test_simultaneous_rejections_do_not_retry_in_lockstep():
    """The point of the change. Undithered, these would be one value; they must not be.

    100 requests rejected in the same instant, bucketed at 100ms. Undithered they land in
    a single bucket and re-hammer the endpoint together.
    """
    buckets = {round(_jittered(2.0, 1), 1) for _ in range(100)}
    assert len(buckets) >= 8


def test_rate_limit_errors_are_still_classified_as_transient():
    """The jitter is unreachable if classification regresses, so pin that too."""
    for msg in ("429 Too Many Requests", "rate limit exceeded", "503 Service Unavailable",
                "connection reset by peer", "RESOURCE_EXHAUSTED"):
        assert _is_transient(msg), msg
    # a permanent error whose text embeds a retryable-looking number must not retry
    assert not _is_transient("400 invalid request: resulted in 16500 tokens")
