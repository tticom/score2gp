"""Public fixtures test version stamping infrastructure, not musical fidelity."""

import ast
import inspect

import pytest

from score2gp import gp_package
from score2gp.ir import SCHEMA_VERSION, ScoreBooklet, ScoreIR


@pytest.mark.parametrize("function,model", [
    (gp_package.extract_score_ir_from_gp, "ScoreBooklet"),
    (gp_package._extract_score_ir_from_relational_gpif_root, "ScoreIR"),
    (gp_package._extract_score_ir_from_gpif_root, "ScoreIR"),
])
def test_gp_import_constructors_use_schema_constant(function, model):
    # Mutant: freeze any constructor to a literal, including today's version.
    tree = ast.parse(inspect.getsource(function))
    constructors = [node for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == model]
    assert len(constructors) == 1
    versions = [kw.value for kw in constructors[0].keywords
                if kw.arg == "schema_version"]
    assert len(versions) == 1
    assert isinstance(versions[0], ast.Name)
    assert versions[0].id == "SCHEMA_VERSION"


@pytest.mark.parametrize("layout", ["legacy", "relational"])
@pytest.mark.parametrize("booklet", [False, True], ids=["score", "booklet"])
def test_gp_import_stamps_current_schema_version(tmp_path, layout, booklet):
    # Mutant: retain an old version in any importer or booklet movement.
    if booklet:
        original = ScoreBooklet.from_json_file(
            "fixtures/public/test_gpif_score_booklets.ir.json"
        )
    else:
        original = ScoreIR.from_json_file("fixtures/public/tiny_score.ir.json")
    package = tmp_path / "import.gp"
    gp_package.write_gp(original, package, gpif_layout=layout)
    imported = gp_package.extract_score_ir_from_gp(package)
    assert isinstance(imported, type(original))
    assert imported.schema_version == SCHEMA_VERSION
    if booklet:
        assert len(imported.scores) == len(original.scores)
        assert all(score.schema_version == SCHEMA_VERSION for score in imported.scores)
