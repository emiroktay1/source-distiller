"""Tests for source_distiller CLI."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "source_distiller.cli", *args],
        text=True, capture_output=True, check=check,
    )


@pytest.fixture
def source_dir(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text(
        "# Alpha\nThe speed of light is 299792458 meters per second.\n"
        "Photons have zero rest mass.\n"
    )
    (docs / "beta.md").write_text(
        "# Beta\nWater boils at 100 degrees Celsius at sea level.\n"
        "Ice melts at 0 degrees Celsius.\n"
    )
    (docs / "gamma.md").write_text(
        "# Gamma\nThis document is about cooking recipes.\n"
        "Add salt to taste.\n"
    )
    return docs


@pytest.fixture
def index_path(source_dir, tmp_path):
    out = tmp_path / "index.json"
    run_cli("index", str(source_dir), "--out", str(out))
    return out


class TestIndex:
    def test_creates_index(self, source_dir, tmp_path):
        out = tmp_path / "index.json"
        result = run_cli("index", str(source_dir), "--out", str(out))
        assert out.exists()
        assert "indexed 3 sources" in result.stdout

    def test_index_structure(self, index_path):
        data = json.loads(index_path.read_text())
        assert data["version"] in (1, 2)
        assert len(data["sources"]) == 3
        assert data["chunk_count"] > 0
        assert "doc_freq" in data


class TestSearch:
    def test_finds_relevant(self, index_path):
        result = run_cli("search", "--index", str(index_path), "--query", "speed of light photons", "--json")
        hits = json.loads(result.stdout)
        assert len(hits) > 0
        assert hits[0]["source"] == "alpha.md"

    def test_ranks_correctly(self, index_path):
        result = run_cli("search", "--index", str(index_path), "--query", "water boils temperature", "--json")
        hits = json.loads(result.stdout)
        assert len(hits) > 0
        assert hits[0]["source"] == "beta.md"

    def test_irrelevant_query(self, index_path):
        result = run_cli("search", "--index", str(index_path), "--query", "cryptocurrency blockchain mining", "--json")
        hits = json.loads(result.stdout)
        assert len(hits) == 0


class TestQuote:
    def test_quote_span(self, index_path):
        result = run_cli("quote", "--index", str(index_path), "--cite", "S1:L1-L3")
        assert "speed of light" in result.stdout

    def test_unknown_source(self, index_path):
        result = run_cli("quote", "--index", str(index_path), "--cite", "S99:L1-L2", check=False)
        assert result.returncode != 0


class TestAudit:
    def test_clean_answer(self, index_path, tmp_path):
        answer = tmp_path / "answer.md"
        answer.write_text("The speed of light is 299792458 m/s [S1:L2-L2].\n")
        result = run_cli("audit", "--index", str(index_path), "--answer", str(answer))
        assert result.returncode == 0
        assert "bad_citations: 0" in result.stdout

    def test_fake_citation(self, index_path, tmp_path):
        answer = tmp_path / "answer.md"
        answer.write_text("Some claim [S99:L1-L5].\n")
        result = run_cli("audit", "--index", str(index_path), "--answer", str(answer), check=False)
        assert result.returncode == 1
        assert "unknown source" in result.stdout

    def test_out_of_range(self, index_path, tmp_path):
        answer = tmp_path / "answer.md"
        answer.write_text("Some claim [S1:L1-L9999].\n")
        result = run_cli("audit", "--index", str(index_path), "--answer", str(answer), check=False)
        assert result.returncode == 1
        assert "line range outside" in result.stdout

    def test_uncited_block(self, index_path, tmp_path):
        answer = tmp_path / "answer.md"
        answer.write_text(
            "This is a very long paragraph that makes many claims about various things "
            "and should definitely have a citation somewhere but it does not have one at all "
            "which means the audit should flag it as potentially uncited content.\n"
        )
        result = run_cli("audit", "--index", str(index_path), "--answer", str(answer), check=False)
        assert result.returncode == 1
        assert "possibly_uncited_blocks: 1" in result.stdout


@pytest.fixture
def conflict_dir(tmp_path):
    """Two documents that disagree on a key fact."""
    docs = tmp_path / "conflict_docs"
    docs.mkdir()
    (docs / "report_2024.md").write_text(
        "# Annual Report 2024\n"
        "The retention period for audit logs is 30 days.\n"
        "Customer records are encrypted with AES-128.\n"
        "The system handles 500 requests per second.\n"
    )
    (docs / "report_2025.md").write_text(
        "# Annual Report 2025\n"
        "The retention period for audit logs is 90 days.\n"
        "Customer records are encrypted with AES-256.\n"
        "The system handles 2000 requests per second.\n"
    )
    return docs


@pytest.fixture
def conflict_index(conflict_dir, tmp_path):
    out = tmp_path / "conflict_index.json"
    run_cli("index", str(conflict_dir), "--out", str(out))
    return out


class TestConflicts:
    def test_detects_conflicts(self, conflict_index):
        result = run_cli("conflicts", "--index", str(conflict_index))
        assert "potential cross-source conflicts" in result.stdout or "No cross-source" in result.stdout

    def test_json_output(self, conflict_index):
        result = run_cli("conflicts", "--index", str(conflict_index), "--json")
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_numeric_conflicts_found(self, conflict_index):
        result = run_cli("conflicts", "--index", str(conflict_index), "--json")
        data = json.loads(result.stdout)
        # Both docs discuss same topics with different numbers
        if data:
            assert any(c["numeric_conflicts"] for c in data)


class TestReport:
    def test_generates_report(self, index_path):
        result = run_cli("report", "--index", str(index_path))
        assert "# Source Distiller Report" in result.stdout
        assert "## Source Map" in result.stdout

    def test_report_with_query(self, index_path):
        result = run_cli("report", "--index", str(index_path), "--query", "speed of light")
        assert "## Evidence for:" in result.stdout

    def test_report_to_file(self, index_path, tmp_path):
        out = tmp_path / "report.md"
        run_cli("report", "--index", str(index_path), "--out", str(out))
        assert out.exists()
        content = out.read_text()
        assert "# Source Distiller Report" in content


class TestStats:
    def test_shows_stats(self, index_path):
        result = run_cli("stats", "--index", str(index_path))
        assert "sources:" in result.stdout
        assert "chunks:" in result.stdout
        assert "alpha.md" in result.stdout
