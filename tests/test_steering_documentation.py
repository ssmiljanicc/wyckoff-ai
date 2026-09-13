"""Offline guard for the canonical project steering documents."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
STEERING = PROJECT_ROOT / ".claude" / "steering"
CANONICAL_STEERING = ("product.md", "tech.md", "structure.md")


def test_canonical_steering_documents_exist() -> None:
    for name in CANONICAL_STEERING:
        assert (STEERING / name).is_file(), name


def test_agent_instruction_adapters_point_to_all_steering_documents() -> None:
    for instructions in (PROJECT_ROOT / "CLAUDE.md", PROJECT_ROOT / "AGENTS.md"):
        text = instructions.read_text()
        for name in CANONICAL_STEERING:
            assert f".claude/steering/{name}" in text, (instructions, name)


def test_structure_names_the_canonical_set() -> None:
    text = (STEERING / "structure.md").read_text()
    assert "`product.md`, `tech.md` i `structure.md`" in text


def test_tech_links_the_accepted_preprocessor_decision() -> None:
    decision = PROJECT_ROOT / "docs" / "decisions" / "0001-expert-ingest-preprocessor.md"
    assert decision.is_file()
    assert "0001-expert-ingest-preprocessor.md" in (STEERING / "tech.md").read_text()
    assert "Ne uvoditi Docling" in decision.read_text()
