"""Phase 5 tests — monitoring analytics, detection, notifications.

Deterministic unit tests; mocked provider paths are explicitly test-scoped and
never produce real network calls. Never fabricates data.
"""

from __future__ import annotations

from pricepilot.monitoring.analytics import _trend
from pricepilot.monitoring.detect import _pct, detect_events
from pricepilot.providers.notifications import NoopNotificationProvider
from pricepilot.providers.notifications.registry import build_notification_provider

# ---------- analytics (deterministic) ----------

def test_trend_flat():
    assert _trend([100, 100, 100]) == "flat"


def test_trend_up():
    assert _trend([90, 91, 92]) == "up"


def test_trend_down():
    assert _trend([110, 105, 100]) == "down"


def test_trend_single_returns_none():
    assert _trend([100]) is None


def test_pct():
    assert _pct(100, 90) == -10.0
    assert _pct(100, 110) == 10.0
    assert _pct(None, 90) is None
    assert _pct(0, 90) is None


# ---------- detection (test-scoped fake session, never real DB) ----------

class _Rows:
    def __init__(self, dicts):
        self._dicts = list(dicts)
        self._i = 0
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self._i >= len(self._dicts):
            raise StopAsyncIteration
        r = _Map(self._dicts[self._i])
        self._i += 1
        return r
    def mappings(self):
        # return an object that supports .all() and .first()
        return _MappingResult(self._dicts)


class _MappingResult:
    def __init__(self, dicts):
        self._dicts = list(dicts)
    def all(self):
        return [_Map(d) for d in self._dicts]
    def first(self):
        return _Map(self._dicts[0]) if self._dicts else None
    def mappings(self):
        return self
    @property
    def _mapping(self):
        return self


class _Map:
    def __init__(self, d):
        self._d = d
    def __getitem__(self, k):
        return self._d[k]
    def get(self, k, default=None):
        return self._d.get(k, default)


class _FakeSession:
    """Returns canned rows keyed by the SQL fragment in the query."""

    def __init__(self, *, prior=None, prior_min=None):
        self._prior = prior
        self._prior_min = prior_min

    async def execute(self, stmt, params):
        sql = str(stmt)
        if "MIN(amount)" in sql:
            return _MappingResult([{"m": self._prior_min}] if self._prior_min is not None else [])
        if "ORDER BY recorded_at DESC LIMIT 1" in sql:
            return _MappingResult([self._prior] if self._prior else [{"amount": None}])
        return _MappingResult([])

    def commit(self):
        return None


async def test_detect_price_drop_and_new_low():
    s = _FakeSession(prior={"amount": 100}, prior_min=95.0)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=90,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
    )
    kinds = {e.event_type for e in events}
    assert "price_drop" in kinds      # 90 < previous 100
    assert "new_low" in kinds          # 90 < prior_min 95


async def test_detect_target_price_reached():
    s = _FakeSession(prior={"amount": 120}, prior_min=90.0)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=88,
        currency="USD", target_price=90, source="test",
        observed_at=None, event_scope="wl:x",
    )
    kinds = {e.event_type for e in events}
    assert "target_price_reached" in kinds


async def test_detect_no_events_when_price_rises():
    s = _FakeSession(prior={"amount": 100}, prior_min=90.0)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=110,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
    )
    assert events == []  # no drop, no new low, no target


async def test_detect_no_new_low_without_prior_min():
    # Prior existence but prior_min None → no new_low claim (must be supported)
    s = _FakeSession(prior={"amount": 100}, prior_min=None)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=90,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
    )
    kinds = {e.event_type for e in events}
    assert "new_low" not in kinds      # cannot claim lowest ever without history
    assert "price_drop" in kinds


async def test_detect_none_price_emits_no_events():
    s = _FakeSession(prior=None, prior_min=None)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=None,
        currency="USD", target_price=50, source="test",
        observed_at=None, event_scope="wl:x",
    )
    assert events == []  # no fabricated price events


async def test_detect_back_in_stock():
    # prior unavailable, now available → availability_change fires even without
    # a price signal (no fabricated price event, but an honest transition).
    s = _FakeSession(prior={"amount": None}, prior_min=None)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=None,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
        prior_available=False, current_available=True,
    )
    kinds = {e.event_type for e in events}
    assert "availability_change" in kinds
    assert len(events) == 1  # no other (fabricated) event


async def test_detect_no_back_in_stock_without_prior():
    # No prior state → cannot claim a transition (never fabricated).
    s = _FakeSession(prior=None, prior_min=None)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=90,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
        prior_available=None, current_available=True,
    )
    assert all(e.event_type != "availability_change" for e in events)


async def test_detect_no_back_in_stock_when_becoming_unavailable():
    # available → unavailable is NOT a back-in-stock event.
    s = _FakeSession(prior={"amount": 100}, prior_min=95.0)
    events = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=100,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
        prior_available=True, current_available=False,
    )
    assert all(e.event_type != "availability_change" for e in events)


async def test_event_keys_stable_for_dedup():
    s = _FakeSession(prior={"amount": 100}, prior_min=95.0)
    e1 = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=90,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
    )
    e2 = await detect_events(
        s, product_id="p1", offer_id="o1", current_price=90,
        currency="USD", target_price=None, source="test",
        observed_at=None, event_scope="wl:x",
    )
    keys1 = {e.event_key for e in e1}
    keys2 = {e.event_key for e in e2}
    assert keys1 == keys2  # same event → same key


# ---------- notification provider (honest unavailable) ----------

async def test_noop_notification_available_false():
    assert await NoopNotificationProvider().available() is False


async def test_noop_notification_deliver_honest():
    d = await NoopNotificationProvider().deliver(user_id="u", title="t", body="b")
    assert d.status == "unavailable"
    assert "not" in (d.reason or "").lower()


async def test_unconfigured_registry_returns_noop():
    # PRICEPILOT_NOTIFICATION_PROVIDER defaults to empty → honest no-op
    assert isinstance(build_notification_provider(), NoopNotificationProvider)


# ---------- alert metadata helpers (deterministic) ----------

def test_triggering_offer_payload_price_event():
    from pricepilot.monitoring.alerts import _triggering_offer_payload

    payload = _triggering_offer_payload("price_drop", 45.0, 50.0, "openfoodfacts", "EUR")
    assert payload["event_type"] == "price_drop"
    assert payload["current_price"] == 45.0
    assert payload["previous_price"] == 50.0


def test_triggering_offer_payload_none_for_no_price():
    from pricepilot.monitoring.alerts import _triggering_offer_payload

    assert _triggering_offer_payload("availability_change", None, None, "off", "EUR") is None


def test_pct_threshold_only_for_price_drop():
    from pricepilot.monitoring.alerts import _pct_threshold_from_event

    assert _pct_threshold_from_event("price_drop", -10.0) == -10.0
    assert _pct_threshold_from_event("target_price_reached", -5.0) is None
    assert _pct_threshold_from_event("availability_change", None) is None


def test_kind_for_back_in_stock():
    from pricepilot.monitoring.alerts import _kind_for

    assert _kind_for("availability_change") == "back_in_stock"
    assert _kind_for("price_drop") == "percent_drop"
    assert _kind_for("target_price_reached") == "target_price"
    assert _kind_for("new_low") == "target_price"


# ---------- preferences helpers ----------

def test_preferences_param_value_jsonb():
    from pricepilot.services.preferences import _param_value

    assert _param_value("min_specs", {"storage_gb": 256}) == '{"storage_gb": 256}'
    assert _param_value("max_budget", 500) == 500
    assert _param_value("max_budget", None) is None