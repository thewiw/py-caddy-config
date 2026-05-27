"""Tests – MatchCriteria."""
import pytest
from pydantic import ValidationError

from caddyconfig import MatchCriteria


class TestMatchCriteriaValidation:
    """Pydantic validation at construction time."""

    def test_empty_is_valid(self):
        assert MatchCriteria().to_dict() == {}

    def test_host_valid(self):
        m = MatchCriteria(host=["foo.com", "foo.fr"])
        assert m.to_dict()["host"] == ["foo.com", "foo.fr"]

    def test_host_empty_string_raises(self):
        with pytest.raises(ValidationError, match="non-empty"):
            MatchCriteria(host=[""])

    def test_host_blank_string_raises(self):
        with pytest.raises(ValidationError, match="non-empty"):
            MatchCriteria(host=["   "])

    def test_path_valid(self):
        m = MatchCriteria(path=["/api", "/v1/*"])
        assert m.to_dict()["path"] == ["/api", "/v1/*"]

    def test_path_without_slash_raises(self):
        with pytest.raises(ValidationError, match="'/'"):
            MatchCriteria(path=["api/no-slash"])

    def test_path_empty_string_raises(self):
        with pytest.raises(ValidationError, match="'/'"):
            MatchCriteria(path=[""])

    def test_header_valid(self):
        m = MatchCriteria(header={"X-Auth": ["Bearer"]})
        assert m.to_dict()["header"] == {"X-Auth": ["Bearer"]}

    def test_header_empty_key_raises(self):
        with pytest.raises(ValidationError, match="not be empty"):
            MatchCriteria(header={"": ["value"]})

    def test_header_blank_key_raises(self):
        with pytest.raises(ValidationError, match="not be empty"):
            MatchCriteria(header={"   ": ["value"]})

    def test_path_regexp(self):
        m = MatchCriteria(path_regexp={"name": "ver", "pattern": "^/v[0-9]+"})
        assert m.to_dict()["path_regexp"]["pattern"] == "^/v[0-9]+"

    def test_header_regexp(self):
        m = MatchCriteria(header_regexp={"name": "r1", "field": "X-Foo", "pattern": "^val"})
        assert m.to_dict()["header_regexp"]["field"] == "X-Foo"

    def test_query_valid(self):
        m = MatchCriteria(query={"key": ["value"], "topic": ["api"]})
        assert m.to_dict()["query"] == {"key": ["value"], "topic": ["api"]}

    def test_query_empty_key_raises(self):
        with pytest.raises(ValidationError, match="not be empty"):
            MatchCriteria(query={"": ["value"]})

    def test_query_blank_key_raises(self):
        with pytest.raises(ValidationError, match="not be empty"):
            MatchCriteria(query={"   ": ["value"]})

    def test_not_matcher(self):
        inner = MatchCriteria(path=["/health"])
        m = MatchCriteria(not_=[inner])
        assert m.to_dict() == {"not": [{"path": ["/health"]}]}


class TestMatchCriteriaSerialization:
    """Serialization / deserialization."""

    def test_none_fields_omitted(self):
        m = MatchCriteria(host=["foo.com"])
        d = m.to_dict()
        assert "path" not in d
        assert "header" not in d

    def test_from_dict_host_and_path(self):
        m = MatchCriteria.from_dict({"host": ["foo.com"], "path": ["/api"]})
        assert m.host == ["foo.com"]
        assert m.path == ["/api"]

    def test_from_dict_not_keyword(self):
        m = MatchCriteria.from_dict({"not": [{"path": ["/skip"]}]})
        assert m.not_ is not None
        assert m.not_[0].path == ["/skip"]

    def test_from_dict_query(self):
        m = MatchCriteria.from_dict({"query": {"key": ["value"]}})
        assert m.query == {"key": ["value"]}

    def test_roundtrip_full(self):
        m = MatchCriteria(
            host=["foo.com"],
            path=["/api"],
            header={"X-Key": ["v"]},
            query={"key": ["value"]},
            not_=[MatchCriteria(path=["/skip"])],
        )
        m2 = MatchCriteria.from_dict(m.to_dict())
        assert m2.to_dict() == m.to_dict()


class TestMatchCriteriaMatchesExactly:
    """Matching logic used by find / upsert / remove."""

    def test_host_exact(self):
        route = MatchCriteria(host=["foo.com", "foo.fr"])
        assert route.matches_exactly(MatchCriteria(host=["foo.com", "foo.fr"])) is True

    def test_host_order_independent(self):
        route = MatchCriteria(host=["foo.fr", "foo.com"])
        assert route.matches_exactly(MatchCriteria(host=["foo.com", "foo.fr"])) is True

    def test_host_mismatch(self):
        route = MatchCriteria(host=["foo.com"])
        assert route.matches_exactly(MatchCriteria(host=["bar.com"])) is False

    def test_none_criteria_ignored(self):
        """A None field in the criteria is ignored (wildcard)."""
        route = MatchCriteria(host=["foo.com"], path=["/app1"])
        # Searching by host only → path is ignored → True
        assert route.matches_exactly(MatchCriteria(host=["foo.com"])) is True

    def test_path_mismatch_when_specified(self):
        route = MatchCriteria(host=["foo.com"], path=["/app1"])
        assert route.matches_exactly(MatchCriteria(host=["foo.com"], path=["/other"])) is False

    def test_full_host_and_path(self):
        route = MatchCriteria(host=["foo.com"], path=["/app1"])
        assert route.matches_exactly(MatchCriteria(host=["foo.com"], path=["/app1"])) is True

    def test_path_order_independent(self):
        route = MatchCriteria(path=["/b", "/a"])
        assert route.matches_exactly(MatchCriteria(path=["/a", "/b"])) is True

    def test_empty_criteria_matches_empty_route(self):
        assert MatchCriteria().matches_exactly(MatchCriteria()) is True

    def test_not_matcher_length_mismatch(self):
        route = MatchCriteria(not_=[MatchCriteria(path=["/x"])])
        criteria = MatchCriteria(not_=[MatchCriteria(path=["/x"]), MatchCriteria(path=["/y"])])
        assert route.matches_exactly(criteria) is False

    def test_not_matcher_content_match(self):
        route = MatchCriteria(not_=[MatchCriteria(path=["/health"])])
        criteria = MatchCriteria(not_=[MatchCriteria(path=["/health"])])
        assert route.matches_exactly(criteria) is True

    def test_header_mismatch(self):
        route = MatchCriteria(header={"X-A": ["v1"]})
        assert route.matches_exactly(MatchCriteria(header={"X-A": ["v2"]})) is False

    def test_query_exact(self):
        route = MatchCriteria(query={"key": ["value"]})
        assert route.matches_exactly(MatchCriteria(query={"key": ["value"]})) is True

    def test_query_mismatch(self):
        route = MatchCriteria(query={"key": ["value"]})
        assert route.matches_exactly(MatchCriteria(query={"key": ["other"]})) is False

    def test_none_criteria_ignores_query(self):
        route = MatchCriteria(host=["foo.com"], query={"key": ["value"]})
        assert route.matches_exactly(MatchCriteria(host=["foo.com"])) is True