[← README](../../README.md) · [Handbook](../HANDBOOK.md) · [Glossary](../00-glossary.md)

# Architecture decision records

An **architecture decision record (ADR)** is a one-page note that captures
one design decision: the situation, the options, the choice, and what it
commits us to. *Everyday version:* the minutes of the meeting where a
choice was made, so that nobody has to re-argue it a year later — and so
that a newcomer can see *why* the system is shaped the way it is, not only
*how*. My other projects keep the same folder.

Each record has the same sections: **Status**, **Date**, **Context**,
**Decision**, **Alternatives considered**, **Consequences**. Records are
never edited after acceptance; a change of mind is a new record that
supersedes the old one.

| # | Decision | Status |
|---|---|---|
| [0001](0001-authentication-ladder.md) | Authentication is added as a ladder — token gate, local accounts, single sign-on — behind one feature flag, with single sign-on as the destination | proposed |

Decisions made before this folder existed live in the documents that made
them: the one design rule in [`02-architecture.md`](../02-architecture.md#the-one-design-rule-everything-else-follows-from),
the two-repository layout in [`03-git-workflow.md`](../03-git-workflow.md),
the identification rule in [`09-chemical-identification.md`](../09-chemical-identification.md).
New records are added by the phase that makes the decision and listed in
the phase's tutorial.

**Last Updated:** September 8, 2026
