"""Located resource limits for retained PDF inspection data."""

from typing import Any


# Count JSON value occurrences, not object identities: repeated references are
# expanded repeatedly by the inspection serializer. See the PERF-01 design
# receipt for the measured corpus envelope and Windows working-set measurements.
INSPECTION_PAGE_NODE_LIMIT = 2_000_000
INSPECTION_BUDGET_CODE = "pdf_resource_inspection_page_nodes_exceeded"


class PdfInspectionResourceLimit(RuntimeError):
    """Inspection would retain more serialized values than its measured budget."""

    def __init__(self, count: int, page_index: int):
        self.count = count
        self.page_index = page_index
        super().__init__(
            f"{INSPECTION_BUDGET_CODE}: inspection_page_nodes={count} "
            f"exceeds limit={INSPECTION_PAGE_NODE_LIMIT} at page_index={page_index}"
        )


def inspection_page_nodes(value: Any) -> int:
    """Count expanded JSON values in O(N) time without serializing their content.

    Each container and scalar is one node; dictionary keys are not nodes.
    References are deliberately visited once per occurrence, as in JSON output.
    Inspection pages are acyclic JSON-compatible structures.
    """
    count = 0
    pending = [value]
    while pending:
        item = pending.pop()
        count += 1
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)
    return count


def check_inspection_budget(count: int, page_index: int) -> None:
    """Stop before retaining the next page or allocating the document JSON string."""
    if count > INSPECTION_PAGE_NODE_LIMIT:
        raise PdfInspectionResourceLimit(count, page_index)
