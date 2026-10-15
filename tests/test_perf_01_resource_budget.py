"""Budget-counter infrastructure only; no notation or fidelity claim.

Scalable containers are the only public CI input for growth without the private
corpus. These checks supplement, and carry no domain acceptance weight beside,
the real-source tests in test_perf_01_private.py.
"""

from score2gp.pdf_resource_budget import inspection_page_nodes


def test_counting_serialized_occurrences_grows_linearly():
    # Repeated references expand repeatedly in JSON, so identities cannot be
    # deduplicated when charging the serialization budget.
    item = {"counts": [1, 2, 3]}
    small = inspection_page_nodes([item] * 1000)
    large = inspection_page_nodes([item] * 2000)
    assert small == 5001
    assert large == 10001
    assert large / small <= 2
