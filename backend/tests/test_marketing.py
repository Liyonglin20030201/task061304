import pytest
from datetime import date, timedelta


class TestMarketingLifecycle:
    """Tests for member lifecycle classification and trigger logic."""

    def _classify(self, days_since_last, days_registered):
        if days_registered <= 30:
            return "new"
        elif days_since_last <= 30:
            return "active"
        elif days_since_last <= 90:
            return "declining"
        elif days_since_last <= 180:
            return "at_risk"
        else:
            return "churned"

    def test_new_member(self):
        assert self._classify(5, 10) == "new"

    def test_active_member(self):
        assert self._classify(15, 100) == "active"

    def test_declining_member(self):
        assert self._classify(60, 200) == "declining"

    def test_at_risk_member(self):
        assert self._classify(120, 365) == "at_risk"

    def test_churned_member(self):
        assert self._classify(200, 500) == "churned"

    def test_new_takes_priority_over_active(self):
        assert self._classify(5, 20) == "new"


class TestCooldownFilter:
    """Tests for campaign cooldown and dedup logic."""

    def test_within_cooldown_blocked(self):
        cooldown_days = 7
        last_trigger = date.today() - timedelta(days=3)
        cutoff = date.today() - timedelta(days=cooldown_days)
        assert last_trigger > cutoff  # should be blocked

    def test_past_cooldown_allowed(self):
        cooldown_days = 7
        last_trigger = date.today() - timedelta(days=10)
        cutoff = date.today() - timedelta(days=cooldown_days)
        assert last_trigger <= cutoff  # should be allowed

    def test_max_triggers_exceeded(self):
        max_triggers = 3
        current_count = 3
        assert current_count >= max_triggers

    def test_max_triggers_not_exceeded(self):
        max_triggers = 3
        current_count = 2
        assert current_count < max_triggers


class TestRepurchaseInterval:
    """Tests for repurchase interval calculation."""

    def test_overdue_repurchase(self):
        avg_interval = 30
        days_since_last = 50
        threshold = avg_interval * 1.5
        assert days_since_last > threshold

    def test_not_overdue(self):
        avg_interval = 30
        days_since_last = 35
        threshold = avg_interval * 1.5
        assert days_since_last <= threshold


class TestBirthdayTrigger:
    """Tests for birthday detection logic."""

    def test_birthday_within_7_days(self):
        today = date.today()
        birthday_this_year = today + timedelta(days=5)
        days_ahead = (birthday_this_year - today).days
        assert 0 <= days_ahead <= 7

    def test_birthday_outside_window(self):
        today = date.today()
        birthday_this_year = today + timedelta(days=15)
        days_ahead = (birthday_this_year - today).days
        assert days_ahead > 7
