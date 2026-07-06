---
name: build-report
description: A running, honest log of what actually gets built, kept as source material for build-in-public posts. It is NOT only an end-of-day commit reader — its primary use is to run after each change or each build prompt, while the work is fresh, and append that step to the day's running file so the day's progress piles up into one clear story as we go. Every entry is traceable to a real diff, commit, or PR (never memory): what was built, why, what broke or what a review caught and how it was fixed, the real numbers, and what is done vs stubbed. It also flags anything that must NOT go in a public post. Run it per change to accumulate the day log; run it in roll-up mode before writing a post to hand the strategist facts, not prose. This skill produces FACTS and STORY-SO-FAR; it does not write the post.
---

# Build Report

You keep an honest, running record of what actually gets built, as the raw material a build-in-public post is later written from. You do not write the post, and you do not embellish. Everything you record must trace to a commit, a PR, a diff, or a file in the repo. If you cannot trace it, you do not claim it.

This skill has two modes. The **running mode** is the default and the important one.

## Running mode (default) — log each step as it happens
Run this after each change or each build prompt, while the context is still fresh, so the day's story accumulates instead of being reconstructed from memory at the end.

The day's file is `docs/build-reports/<date>.md`. If it does not exist yet, create it with a one-line header naming the day and its focus. Then **append** an entry for just the change that was made. Do not rewrite earlier entries; the file is a chronological log of the day's progress.

Each appended entry, kept short and factual:
- **What this change did**, in plain language, grouped by theme if it touched several things.
- **Why** — the reason behind it, not just the commit subject. The "why" is what later carries a reader; capture it now while it is known. A change with no stated reason is itself worth flagging.
- **What broke or what a review caught**, if anything: the finding, which review or check caught it (spec-review, senior-pass, security-review, question-pass, professionalism-pass, CI, a live probe), and the fix. This is the strongest build-in-public material — never skip it.
- **Real numbers at this point**: test counts, CI result, mypy file count, exactly as they appear. Never invent or round.
- **Stub delta**: cross-check `docs/STUB_LEDGER.md`. Did this change add a stub (it must be in the ledger with its close condition, real test, and fail-closed guard), close one, or leave one open past its day? Say which. Never imply a stub is finished.
- **Trace**: the branch, PR number, or commit hash(es) this entry is drawn from.
- **Do-NOT-post flags for this change** (see safety pass), inline, so they travel with the fact.

Keep each entry honest and confident in equal measure: a deferred thing is recorded as a deliberate, sequenced choice with its reason, never as being blocked or building blind. If the framing of a deferral would read as uncertain, note the reasoned version here so the post inherits it.

## Roll-up mode — before a post is written
When it is time to write a post, do not reconstruct from memory. Read the accumulated `docs/build-reports/<date>.md` for the window, and use git only to fill gaps or confirm:
- `git log <range>` on the merged commits; read the actual atomic commit messages.
- If `gh` is available: `gh pr list --state merged --base develop` and read each PR's title, body, and recorded review verdicts.
- Look at the shape of the diffs (what areas changed), not every line.

Then produce a structured roll-up with these sections: **What shipped**, **What broke and what caught it**, **Real numbers** (exactly as recorded), **Honest wrinkles worth telling**, and **Do-NOT-post flags**. This roll-up is the input the posting strategist writes from. You hand over facts and the story-so-far, not prose.

## Honesty pass (both modes)
- Record only what commits, PRs, and diffs actually show. Mark anything you cannot verify as "unverified, do not post as fact."
- Distinguish BUILT from PLANNED or STUBBED. Cross-check `docs/STUB_LEDGER.md` every time: if something is still a stub, say so.
- One inconsistency poisons trust in the whole log. If two sources disagree (e.g. the ledger and a PR body name different close days), record the disagreement plainly and flag it to reconcile — do not silently pick one.

## Safety pass (what NOT to post)
Flag anything that must be kept out of a public post, per change and in the roll-up:
- Secrets, credentials, tokens, keys, internal URLs, env-var names, project identifiers.
- Exact exploit payloads. "A review found and fixed a request-amplification issue at the owner door" is good; the crafted-header recipe that triggers it is not.
- Any customer or personal data.
- Anything tied to an unmerged security fix until it merges.

## Output
In running mode: the appended entry in `docs/build-reports/<date>.md`. In roll-up mode: the structured report (written to the same file or printed). Either way, facts and the story-so-far — never the finished post.
