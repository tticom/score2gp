import types

import windows_host_quarantine as q


def _item(nodeid):
    marks = []
    return types.SimpleNamespace(nodeid=nodeid, marks=marks, add_marker=marks.append)


def test_quarantine_marks_exact_ids_strict_on_windows_only():
    listed = sorted(q.QUARANTINED_IDS)[0]
    near_miss = [listed + "_x", listed.rsplit("::", 1)[0], "tests/other.py::" + listed.split("::")[1]]
    items = [_item(listed)] + [_item(n) for n in near_miss]
    q.apply_quarantine(items, platform="win32")
    assert [m.kwargs["strict"] for m in items[0].marks] == [True]
    assert all(not i.marks for i in items[1:])  # rejects prefix/wildcard matching
    posix = [_item(listed)]
    q.apply_quarantine(posix, platform="linux")
    assert not posix[0].marks  # rejects quarantining off the Windows host


def test_quarantine_ids_are_exact_node_ids_without_wildcards():
    assert len(q.QUARANTINED_IDS) == 13
    assert all("::" in i and "*" not in i and "?" not in i for i in q.QUARANTINED_IDS)
