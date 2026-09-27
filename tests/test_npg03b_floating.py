from pathlib import Path

import pytest

from score2gp.build_ir import BuildIrInputRiskError, build_ir_from_tabraw_only
from score2gp.notation_omr.note_duration import read_note_durations
from score2gp.pdf import extract_tab
from score2gp.tabraw import TabRaw

def test_private_acceptance_melodic(tmp_path):
    pdf_path = Path("fixtures/private/Melodic Soloing Masterclass.pdf")
    if not pdf_path.exists():
        pytest.skip("mounted private corpus is unavailable: Melodic Soloing Masterclass.pdf")

    tabraw_path = tmp_path / "melodic.tabraw.json"
    tabraw = TabRaw.model_validate(extract_tab(pdf_path, tabraw_path))

    # Prove that we have floating barlines extracted
    assert len(tabraw.floating_barlines) > 0

    # This PDF has TAB but no notation staff: DUR-01 cannot supply any note types.
    records = read_note_durations(pdf_path)
    assert records["systems"] == []
    with pytest.raises(BuildIrInputRiskError) as refusal:
        build_ir_from_tabraw_only(tabraw_path)
    assert refusal.value.category == "pdf_only_tab_note_durations_missing"
    assert refusal.value.stage == "note-type-route"

    # NEGATIVE CONTROL: Prove that standard barlines from the genuine source PDF are ignored.
    # If standard barlines were incorrectly treated as floating barlines, we'd have dozens of them.
    # Furthermore, none of the valid floating barlines in this specific PDF are in the left margin (<200.0)
    # where standard start-of-system barlines exist.
    assert len(tabraw.floating_barlines) == 11
    for fb in tabraw.floating_barlines:
        assert fb.x > 200.0
