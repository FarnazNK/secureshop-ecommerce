"""Circuit breaker for calls to external services (Stripe).

Without one, a slow or failing dependency makes every request wait for its
timeout, workers pile up, and the whole API degrades. With one, after a few
failures in a short window we stop calling the dependency for a cooldown and
fail fast with a clear "temporarily unavailable" error instead.

States:
    CLOSED     normal; failures are counted in a sliding window
    OPEN       calls are rejected immediately until the cooldown ends
    HALF_OPEN  one trial call is allowed; success closes, failure re-opens

State is per process (like Hystrix / resilience4j defaults). On serverless each
instance trips independently, which still protects each instance; see
docs/SCALING.md for sharing state through Redis at larger scale.
"""

from __future__ import annotations

import enum
import time
from collections import deque
from collections.abc import Callable

from prometheus_client import Counter, Gauge

CIRCUIT_STATE = Gauge(
    "secureshop_circuit_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["name"],
)
CIRCUIT_REJECTIONS = Counter(
    "secureshop_circuit_rejections_total", "Calls rejected while the circuit was open", ["name"]
)
CIRCUIT_OPENED = Counter("secureshop_circuit_opened_total", "Times the circuit opened", ["name"])


class CircuitState(enum.IntEnum):
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


class CircuitOpenError(Exception):
    """Raised instead of calling the dependency while the circuit is open."""

    def __init__(self, name: str, retry_after: int) -> None:
        super().__init__(f"{name} is temporarily unavailable")
        self.name = name
        self.retry_after = retry_after


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        window_seconds: float = 60.0,
        reset_timeout_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.reset_timeout_seconds = reset_timeout_seconds
        self._clock = clock
        self._failures: deque[float] = deque()
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0
        self._trial_in_flight = False
        CIRCUIT_STATE.labels(name).set(CircuitState.CLOSED)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._cooldown_left() <= 0:
            return CircuitState.HALF_OPEN
        return self._state

    def _cooldown_left(self) -> float:
        return self._opened_at + self.reset_timeout_seconds - self._clock()

    def _set(self, state: CircuitState) -> None:
        self._state = state
        CIRCUIT_STATE.labels(self.name).set(state)

    def before_call(self) -> None:
        """Raise CircuitOpenError if the call must not go ahead."""
        if self._state == CircuitState.OPEN:
            left = self._cooldown_left()
            if left > 0:
                CIRCUIT_REJECTIONS.labels(self.name).inc()
                raise CircuitOpenError(self.name, max(1, int(left + 0.999)))
            self._set(CircuitState.HALF_OPEN)
        if self._state == CircuitState.HALF_OPEN:
            if self._trial_in_flight:
                CIRCUIT_REJECTIONS.labels(self.name).inc()
                raise CircuitOpenError(self.name, 1)
            self._trial_in_flight = True

    def record_success(self) -> None:
        self._trial_in_flight = False
        self._failures.clear()
        if self._state != CircuitState.CLOSED:
            self._set(CircuitState.CLOSED)

    def record_failure(self) -> None:
        now = self._clock()
        self._trial_in_flight = False
        if self._state == CircuitState.HALF_OPEN:
            self._open(now)
            return
        self._failures.append(now)
        while self._failures and now - self._failures[0] > self.window_seconds:
            self._failures.popleft()
        if len(self._failures) >= self.failure_threshold:
            self._open(now)

    def _open(self, now: float) -> None:
        self._opened_at = now
        self._failures.clear()
        self._set(CircuitState.OPEN)
        CIRCUIT_OPENED.labels(self.name).inc()

    def abandon_trial(self) -> None:
        """The call never finished (e.g. request cancelled): free the half-open
        slot without counting it as a success or a failure."""
        self._trial_in_flight = False

    def reset(self) -> None:
        self._failures.clear()
        self._trial_in_flight = False
        self._set(CircuitState.CLOSED)
