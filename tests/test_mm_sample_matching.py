"""One MM-file pattern matcher shared by every resolver (#193).

Process External Data dropped every '*' and did a plain substring match, and
split patterns only on commas; the main matcher honoured where the '*' sat and
also split on semicolons, tabs and new lines — so the same compound list could
select different MM files and change the background correction and the MRRF.
"""

import pytest

from manic.io.in_memory_provider import InMemoryDataProvider
from manic.io.mm_matching import (
    mm_token_matches,
    parse_mm_tokens,
    resolve_mm_samples_from_names,
)


class TestParseTokens:
    def test_splits_on_commas_semicolons_tabs_and_newlines(self):
        assert parse_mm_tokens("MM1, MM2;MM3\tMM4\nMM5") == ["MM1", "MM2", "MM3", "MM4", "MM5"]

    def test_empty_and_blank(self):
        assert parse_mm_tokens(None) == []
        assert parse_mm_tokens("") == []
        assert parse_mm_tokens("  , ; ") == []


class TestTokenMatching:
    def test_wildcard_anchors_at_both_ends(self):
        assert mm_token_matches("MM*1", "MM1") is True
        assert mm_token_matches("MM*1", "MM10") is False
        assert mm_token_matches("MM*1", "xMM1") is False
        assert mm_token_matches("MM*1", "MM_1") is True

    def test_leading_and_trailing_wildcards(self):
        assert mm_token_matches("*1", "xMM1") is True
        assert mm_token_matches("MM*", "MM_1") is True
        assert mm_token_matches("*1", "MM10") is False

    def test_bare_token_is_a_substring_match(self):
        assert mm_token_matches("MM1", "MM10") is True
        assert mm_token_matches("MM1", "xMM1") is True
        assert mm_token_matches("MM1", "MM2") is False

    def test_case_insensitive(self):
        assert mm_token_matches("mm*1", "MM1") is True
        assert mm_token_matches("MM*1", "mm_1") is True

    def test_like_special_chars_are_literal(self):
        assert mm_token_matches("MM%1*", "MM%1b") is True
        assert mm_token_matches("MM_1*", "MMx1b") is False


class TestResolveFromNames:
    SAMPLES = ["MM1", "MM10", "xMM1", "MM_1"]

    def test_issue_example_selects_like_the_main_matcher(self):
        assert resolve_mm_samples_from_names("MM*1", self.SAMPLES) == ["MM1", "MM_1"]

    def test_bare_token_keeps_substring_semantics(self):
        assert resolve_mm_samples_from_names("MM1", self.SAMPLES) == ["MM1", "MM10", "xMM1"]

    def test_multiple_patterns_union(self):
        assert resolve_mm_samples_from_names("MM*1; MM_2", self.SAMPLES + ["MM_2"]) == [
            "MM1",
            "MM_1",
            "MM_2",
        ]

    def test_no_patterns(self):
        assert resolve_mm_samples_from_names(None, self.SAMPLES) == []
        assert resolve_mm_samples_from_names("", self.SAMPLES) == []


class TestInMemoryProviderUsesSharedMatcher:
    def _provider(self, samples):
        return InMemoryDataProvider(compounds=[], samples=samples, raw_data={})

    def test_issue_example_in_memory_matches_main_matcher(self):
        provider = self._provider(["MM1", "MM10", "xMM1", "MM_1"])
        assert provider.resolve_mm_samples("MM*1") == ["MM1", "MM_1"]

    def test_semicolon_delimited_in_memory(self):
        provider = self._provider(["MM1", "MM2"])
        assert provider.resolve_mm_samples("mm2;mm1") == ["MM1", "MM2"]


class TestSqlProviderUsesSharedMatcher:
    @pytest.fixture()
    def db(self, tmp_path, monkeypatch):
        from manic.models import database

        db_path = tmp_path / "test.db"
        monkeypatch.setattr(database, "DB_FILE", db_path)
        schema = (
            database.SCHEMA_SQL_PATH.read_text(encoding="utf-8")
            if hasattr(database, "SCHEMA_SQL_PATH")
            else None
        )
        from pathlib import Path

        if schema is None:
            schema = Path(__file__).parent.parent / "src" / "manic" / "models" / "schema.sql"
            schema = schema.read_text(encoding="utf-8")
        with database.get_connection() as conn:
            conn.executescript(schema)
            conn.executemany(
                "INSERT INTO samples (sample_name, deleted) VALUES (?, ?)",
                [("MM1", 0), ("MM10", 0), ("xMM1", 0), ("MM_1", 0), ("deletedMM", 1)],
            )
        return db_path

    def test_issue_example_over_the_database(self, db):
        from manic.io.data_provider import DataProvider

        assert DataProvider().resolve_mm_samples("MM*1") == ["MM1", "MM_1"]

    def test_deleted_samples_excluded(self, db):
        from manic.io.data_provider import DataProvider

        assert "deletedMM" not in DataProvider().resolve_mm_samples("*MM*")
