[← README](../../README.md) · [Handbook](../HANDBOOK.md) · [Glossary](../00-glossary.md)

# Figures

Every illustration in this folder is produced by one script,
[`make_figures.py`](make_figures.py), never drawn by hand and pasted.
Regenerate all of them from the repository root:

```bash
python3 docs/img/make_figures.py        # pure Python, no dependencies; writes docs/img/*.svg
```

**Why a script?** A figure is edited by changing text and rerunning; it
carries no hidden metadata; the output is byte-identical on every platform,
so it diffs like code; and the **one symbol per record type** — hexagon for a
chemical, vial for a sample, plate for screening, dose curve for toxicology —
is defined once and means the same thing in every document.

| Figure | Shows | Used in |
|---|---|---|
| `cover_crucible.svg` · `logo_crucible.svg` | The banner and the mark | `README.md` |
| `fig_record_types.svg` | The four record types and how three of them hang off a chemical | `README.md`, handbook §2, playbook Part 0, glossary |
| `fig_doc_is_truth.svg` | One table row: indexed columns beside the `doc` that holds the whole record | handbook §5, `02-architecture.md`, `02-database-schema.md` |
| `fig_request_path.svg` | One request through router, session, store, model | handbook §5, `02-architecture.md` |
| `fig_machine_layout.svg` | Two repositories, three folders, content flowing public → private | handbook §6, `03-git-workflow.md`, playbook Part 8 |
| `fig_change_travels.svg` | The seven-step loop after setup, Mac then VM | handbook §6, `03-git-workflow.md` |
| `fig_two_stage_identification.svg` | Stage 1 (either identifier) versus stage 2 (both must agree) | handbook §9, `09-chemical-identification.md`, playbook Part 4 |
| `fig_container_lunchbox.svg` | The same image on three platforms; what is mounted in and what comes out | the three setup guides, handbook §3 |
| `fig_setup_flow.svg` | Set up once, then the loop | the three setup guides, handbook §3 |
| `fig_timeline.svg` | The milestones on one line | handbook §1 |

The interactive figure — the animated architecture page served at
`/architecture` — is a separate, hand-written file,
[`../architecture-interactive.html`](../architecture-interactive.html),
described in [`02-architecture.md`](../02-architecture.md#interactive-architecture-page).

**Last Updated:** September 7, 2026
