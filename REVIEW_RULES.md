# REVIEW_RULES.md

The reviewer’s job is to protect the project from plausible but wrong progress.

Default stance: sceptical.

A PR with passing tests can still be wrong.
A PR with more diagnostics can still be wrong.
A PR that writes GP files can still be wrong.
A PR that improves one private metric can still be wrong.
A PR that changes the oracle must re-establish the benchmark before claiming progress.

Every review must answer:

1. What exact failure existed before?
2. What exact evidence shows it changed?
3. Did the acceptance target move?
4. If the target moved, was that justified by evidence?
5. Did any project invariant get weakened?
6. Are strict and remediation modes cleanly separated?
7. Is the source pair actually a valid oracle?
8. What would make this PR unsafe to merge?

Never approve because the direction seems promising.
Keep draft until the evidence is coherent.