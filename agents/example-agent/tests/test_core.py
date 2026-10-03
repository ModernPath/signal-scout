from __future__ import annotations

import pytest

from example_core import (
    MAX_TITLE_LENGTH,
    Note,
    extract_hashtags,
    normalize_tags,
    search_notes,
    summarize_offline,
    tag_counts,
)


def _note(title: str, body: str = "", tags=(), created_at: str = "2026-01-01T00:00:00+00:00") -> Note:
    return Note(id=f"note_{title[:4]}", title=title, body=body, tags=tuple(tags), created_at=created_at)


class TestNoteCreate:
    def test_strips_and_normalizes(self):
        note = Note.create("  Call Bob  ", " offer ", "Work, #Sales")
        assert note.title == "Call Bob"
        assert note.body == "offer"
        assert note.tags == ("work", "sales")
        assert note.id.startswith("note_")

    @pytest.mark.parametrize("title", ["", "   ", None])
    def test_requires_title(self, title):
        with pytest.raises(ValueError, match="required"):
            Note.create(title)

    def test_rejects_long_title(self):
        with pytest.raises(ValueError, match=str(MAX_TITLE_LENGTH)):
            Note.create("x" * (MAX_TITLE_LENGTH + 1))

    def test_dict_round_trip(self):
        note = Note.create("A", "b", ["c"])
        assert Note.from_dict(note.to_dict()) == note
        assert note.to_dict()["tags"] == ["c"]


class TestTags:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (None, ()),
            ("", ()),
            ("a, b ,a", ("a", "b")),
            (["#Work", "Big Ideas!"], ("work", "big-ideas")),
            (" , ,", ()),
        ],
    )
    def test_normalize_tags(self, raw, expected):
        assert normalize_tags(raw) == expected

    def test_extract_hashtags(self):
        assert extract_hashtags("Buy milk #shopping #Home") == ("Buy milk", ("shopping", "home"))
        assert extract_hashtags("email a#b stays") == ("email a#b stays", ())

    def test_tag_counts_most_common_first(self):
        notes = [_note("a", tags=["x"]), _note("b", tags=["y", "x"])]
        assert list(tag_counts(notes).items()) == [("x", 2), ("y", 1)]


class TestSearch:
    def test_no_query_returns_newest_first(self):
        old = _note("old", created_at="2026-01-01T00:00:00+00:00")
        new = _note("new", created_at="2026-02-01T00:00:00+00:00")
        assert search_notes([old, new]) == [new, old]

    def test_ranks_title_over_body(self):
        in_body = _note("other", body="milk", created_at="2026-02-01T00:00:00+00:00")
        in_title = _note("milk run", created_at="2026-01-01T00:00:00+00:00")
        assert search_notes([in_body, in_title], "milk") == [in_title, in_body]

    def test_excludes_non_matches_and_filters_tag(self):
        notes = [_note("milk", tags=["home"]), _note("milk too", tags=["work"]), _note("bread")]
        assert [n.title for n in search_notes(notes, "milk", tag="work")] == ["milk too"]

    def test_limit(self):
        notes = [_note(f"n{i}", created_at=f"2026-01-0{i}T00:00:00+00:00") for i in range(1, 5)]
        assert len(search_notes(notes, limit=2)) == 2


def test_summarize_offline():
    assert summarize_offline([]) == "No notes to summarize."
    summary = summarize_offline([_note("Call Bob", tags=["work"]), _note("Ship it", tags=["work"])])
    assert "2 note(s)." in summary
    assert "#work (2)" in summary
    assert "Call Bob" in summary
