from pathlib import Path
import tempfile

import pytest

from score2gp.build_ir import build_ir_from_tabraw_only
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf import extract_tab
from score2gp.tabraw import TabRaw

def test_private_acceptance_melodic():
    pdf_path = Path("fixtures/private/Melodic Soloing Masterclass.pdf")
    if not pdf_path.exists():
        pytest.skip("mounted private corpus is unavailable: Melodic Soloing Masterclass.pdf")

    work = Path("work")
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temp_dir:
        tabraw_path = Path(temp_dir) / "melodic.tabraw.json"
        tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))

        # Prove that we have floating barlines extracted
        assert len(tabraw.floating_barlines) > 0

        # The source has notation: exercise the route with its freshly read note types (DUR-02-FU2).
        records = read_note_durations(pdf_path)
        assert len(records["systems"]) == 3
        assert sum(len(system["bars"]) for system in records["systems"]) == 8
        score, diagnostics = build_ir_from_tabraw_only(tabraw_path, note_durations=records)
        assert len(score.bars) == 8
        assert sum(len(bar.events) for bar in score.bars) == 82
        assert diagnostics.note_type_route["summary"]["written_bars"] == 8
        assert diagnostics.note_type_route["summary"]["refused_bars"] == 0

        # NEGATIVE CONTROL: Prove that standard barlines from the genuine source PDF are ignored.
        # If standard barlines were incorrectly treated as floating barlines, we'd have dozens of them.
        # Furthermore, none of the valid floating barlines in this specific PDF are in the left margin (<200.0)
        # where standard start-of-system barlines exist.
        assert len(tabraw.floating_barlines) == 11
        for fb in tabraw.floating_barlines:
            assert fb.x > 200.0
