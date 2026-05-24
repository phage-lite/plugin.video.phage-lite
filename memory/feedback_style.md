---
name: feedback-style
description: Code style and commit preferences from the user
metadata:
  type: feedback
---

Do not add "Co-Authored-By: Claude" lines to git commit messages.
**Why:** User preference — keep commit history clean.
**How to apply:** Every commit, strip the co-author trailer entirely.

No trailing summary paragraph at end of responses — user can read the diff.
**Why:** Confirmed preference, user finds it redundant.
**How to apply:** End responses with at most one sentence on what's next.
