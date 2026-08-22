import json
from score2gp.build_ir import _attach_symbols_and_techniques
from score2gp.ir import ScoreIR, Bar, Event, Provenance, Note
from score2gp.tabraw import TabRaw

def test_build_ir_structural_signals_injected():
    tabraw = TabRaw.model_construct(
        structural_signals={
            "sections": [
                {
                    "page_index": 1,
                    "system_index": 1,
                    "staff_index": 1,
                    "x0": 50.0,
                    "text": "Chorus"
                }
            ],
            "repeats": [
                {
                    "page_index": 1,
                    "system_index": 1,
                    "staff_index": 1,
                    "x0": 10.0,
                    "direction": "start"
                },
                {
                    "page_index": 1,
                    "system_index": 1,
                    "staff_index": 1,
                    "x0": 100.0,
                    "direction": "end"
                }
            ]
        },
        candidates=[]
    )

    score = ScoreIR.model_construct(
        bars=[
            Bar.model_construct(
                index=1,
                events=[
                    Event.model_construct(
                        id="ev_1",
                        notes=[Note.model_construct()],
                        provenance=[
                            Provenance.model_construct(
                                page=1,
                                system_id="1",
                                raw={"x": 55.0}
                            )
                        ]
                    )
                ],
            )
        ]
    )

    _attach_symbols_and_techniques(score, tabraw)

    assert score.bars[0].marker == "Chorus"
    assert score.bars[0].barline == "repeat-end"
