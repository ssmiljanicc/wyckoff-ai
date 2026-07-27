"""Guard: sprečava povratak na in-process Poligon uvoz posle G2 Faze 4 migracije (#44).

AST-bazirano, ne substring/regex — Aerodrom Faza 3 (#45) je pokazala da substring guard hvata
ilustrativne pomene u komentarima/docstring-ovima (npr. istorijsko objašnjenje porekla ugovora).
Oba migrirana fajla legitimno pominju "poligon" u prozi (D1-D7 arhitektonsko obrazloženje,
#218/#220 konvencija) — substring bi lažno pao na tu prozu. AST proverava STRUKTURU (import
čvorove, string-literal argumente unutar poziva), ne slobodan tekst, pa je imun na taj false
positive po konstrukciji. Poznato ograničenje (pregled-plana, prihvaćeno za ovaj krug): ne
prepoznaje importlib/getattr dinamičke oblike niti sys.path.append (samo .insert), pa je imun na
false-positive stranu, ali ne dokazano potpun na false-negative strani.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDED_FILES = (
    ROOT / "scripts" / "validate_expert_analyses.py",
    ROOT / "scripts" / "kb_ingest.py",
)
FORBIDDEN_IDENTIFIERS = frozenset({"POLIGON_SCRIPTS_DIR", "WYCKOFF_INGEST_RUNNER"})


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_no_validate_kb_core_import() -> None:
    """In-process Poligon uvoz (put 1, ADR 0011 §Ograda) mora ostati nula posle migracije."""
    violations = []
    for path in GUARDED_FILES:
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "validate_kb_core":
                        violations.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.ImportFrom) and node.module == "validate_kb_core":
                violations.append(f"{path}:{node.lineno}")
    assert not violations, f"validate_kb_core uvoz reintrodukovan: {violations}"


def test_no_sys_path_insert_toward_poligon() -> None:
    """`sys.path.insert(...)` poziv (bilo koji argument) — mehanizam koji je omogućavao put 1."""
    violations = []
    for path in GUARDED_FILES:
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "insert"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "path"
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "sys"
            ):
                violations.append(f"{path}:{node.lineno}")
    assert not violations, f"sys.path.insert reintrodukovan: {violations}"


def test_no_forbidden_env_var_identifiers_in_code() -> None:
    """`POLIGON_SCRIPTS_DIR`/`WYCKOFF_INGEST_RUNNER` kao string-literal (npr. unutar
    `os.environ.get(...)`) ili kao ime promenljive — oba puta uklonjena Fazom 4 (ADR 0011
    §Posledice). Proverava REALNE AST čvorove (Name identifikatore i Constant string-literale
    unutar poziva), ne slobodan tekst komentara/docstring-ova."""
    violations = []
    for path in GUARDED_FILES:
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_IDENTIFIERS:
                violations.append(f"{path}:{node.lineno}:{node.id}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in FORBIDDEN_IDENTIFIERS:
                    violations.append(f"{path}:{node.lineno}:{node.value!r}")
    assert not violations, f"zabranjen env-var identifikator reintrodukovan: {violations}"


def test_config_has_no_absolute_poligon_path() -> None:
    """`config/kb_ingest.yaml` ne sme sadržati apsolutnu putanju ka poligon repou. YAML nije
    Python — AST se ne primenjuje; ova provera je NAMERNO uska substring provera na TAČNU
    putanju-literal (`/projekti/poligon`), ne na reč "poligon" — istorijski komentari u istom
    fajlu (npr. "migrirano sa poligon apsolutne putanje u G2 Fazi 4") ostaju dozvoljeni. Ova
    provera NE zamenjuje jednokratnu case-insensitive proznu proveru iz Task 6 Validacije —
    ta dva su namerno različitog obima (pregled-plana nalaz)."""
    config_path = ROOT / "config" / "kb_ingest.yaml"
    text = config_path.read_text(encoding="utf-8")
    assert "/projekti/poligon" not in text, (
        "config/kb_ingest.yaml i dalje sadrži apsolutnu poligon putanju"
    )
