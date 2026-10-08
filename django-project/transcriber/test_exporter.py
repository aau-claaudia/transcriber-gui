import json
from types import SimpleNamespace

import pytest

from transcriber import exporter


@pytest.fixture
def media_root(tmp_path, monkeypatch):
    root = tmp_path / "media"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(exporter, "settings", SimpleNamespace(MEDIA_ROOT=str(root)))
    return root


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _prepare_export_dir(media_root, dir_name):
    (media_root / dir_name / "data").mkdir(parents=True, exist_ok=True)


def test_export_routes_notes(monkeypatch):
    called = {}

    def fake_notes(dir_name, file_path, output_format):
        called["args"] = (dir_name, file_path, output_format)
        return "notes-result"

    monkeypatch.setattr(exporter, "_export_notes", fake_notes)

    result = exporter.export("dirA", "/tmp/notes.json", "notes", "txt", False)

    assert result == "notes-result"
    assert called["args"] == ("dirA", "/tmp/notes.json", "txt")


def test_export_routes_edited_output(monkeypatch):
    called = {}

    def fake_edited(dir_name, file_path, output_format, merged_format):
        called["args"] = (dir_name, file_path, output_format, merged_format)
        return "edited-result"

    monkeypatch.setattr(exporter, "_export_edited_output", fake_edited)

    result = exporter.export("dirB", "/tmp/edited.json", "edited_output", "json", True)

    assert result == "edited-result"
    assert called["args"] == ("dirB", "/tmp/edited.json", "json", True)


def test_export_notes_json_passthrough(media_root):
    result = exporter._export_notes("session1", "/does/not/matter.json", "json")
    assert result == str(media_root / "session1" / "data" / "notes.json")


def test_export_edited_output_json_passthrough_unmerged(media_root):
    result = exporter._export_edited_output("session2", "/does/not/matter.json", "json", False)
    assert result == str(media_root / "session2" / "data" / "edited_output.json")


def test_merge_speakers_merges_adjacent_same_speaker(tmp_path):
    input_path = tmp_path / "edited_output.json"
    _write_json(
        input_path,
        {
            "lines": [
                {
                    "id": 0,
                    "startTime": "00:00:00.000",
                    "endTime": "00:00:01.000",
                    "speakerDesignation": "Speaker 1",
                    "text": "Hello",
                },
                {
                    "id": 1,
                    "startTime": "00:00:01.000",
                    "endTime": "00:00:02.000",
                    "speakerDesignation": "Speaker 1",
                    "text": "world",
                },
                {
                    "id": 2,
                    "startTime": "00:00:02.000",
                    "endTime": "00:00:03.000",
                    "speakerDesignation": "Speaker 2",
                    "text": "next",
                },
            ]
        },
    )

    merged = exporter._merge_speakers(str(input_path))

    assert len(merged["lines"]) == 2
    assert merged["lines"][0]["speakerDesignation"] == "Speaker 1"
    assert merged["lines"][0]["text"] == "Hello world"
    assert merged["lines"][0]["endTime"] == "00:00:02.000"
    assert merged["lines"][1]["speakerDesignation"] == "Speaker 2"


def test_export_notes_txt_writes_file(media_root, tmp_path):
    _prepare_export_dir(media_root, "session3")
    notes_input = tmp_path / "notes.json"
    _write_json(
        notes_input,
        {
            "notes": [
                {"date": "2026-08-31", "note": "First note"},
                {"date": "2026-09-01", "note": "Second note"},
            ]
        },
    )

    out_path = exporter._export_notes("session3", str(notes_input), "txt")

    assert out_path == str(media_root / "session3" / "data" / "notes.txt")
    text = (media_root / "session3" / "data" / "notes.txt").read_text(encoding="utf-8")
    assert "2026-08-31" in text
    assert "First note" in text
    assert "2026-09-01" in text
    assert "Second note" in text


def test_export_edited_output_txt_writes_file(media_root, tmp_path):
    _prepare_export_dir(media_root, "session4")
    edited_input = tmp_path / "edited_output.json"
    _write_json(
        edited_input,
        {
            "lines": [
                {
                    "id": 0,
                    "startTime": "00:00:00.000",
                    "endTime": "00:00:01.000",
                    "speakerDesignation": "Speaker X",
                    "text": "Sample line",
                }
            ]
        },
    )

    out_path = exporter._export_edited_output("session4", str(edited_input), "txt", False)

    assert out_path == str(media_root / "session4" / "data" / "edited_output.txt")
    text = (media_root / "session4" / "data" / "edited_output.txt").read_text(encoding="utf-8")
    assert "00:00:00.000 - 00:00:01.000" in text
    assert "Speaker X" in text
    assert "Sample line" in text


def test_export_unknown_format_returns_empty_string(media_root, tmp_path):
    notes_input = tmp_path / "notes.json"
    _write_json(notes_input, {"notes": []})

    result = exporter._export_notes("session5", str(notes_input), "md")

    assert result == ""


def test_extract_speaker_with_and_without_designation():
    assert exporter.extract_speaker({"speakerDesignation": "Speaker A"}) == "Speaker A"
    assert exporter.extract_speaker({"text": "No speaker key"}) == "Undetermined speaker"

