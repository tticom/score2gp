from score2gp.errors import HumanReadableConversionError

def test_human_readable_conversion_error_formatting():
    err = HumanReadableConversionError(
        "Measure capacity violation.",
        page=2,
        measure=5,
        staff=1
    )
    assert str(err) == "Error at Page 2, Measure 5, Staff 1: Measure capacity violation."

    err2 = HumanReadableConversionError(
        "Unowned note: A note exists without fret/pitch information."
    )
    assert str(err2) == "Error: Unowned note: A note exists without fret/pitch information."

    err3 = HumanReadableConversionError(
        "Unrecognized chord symbol.",
        page=3,
        measure=10,
        voice=2,
        beat=1.5
    )
    assert str(err3) == "Error at Page 3, Measure 10, Voice 2, Beat 1.5: Unrecognized chord symbol."
