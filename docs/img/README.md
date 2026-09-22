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
| `fig_machine_layout.svg` | Two repositories, four folders (authoring, mirror, beta, production), content flowing public → private | handbook §6, `03-git-workflow.md`, playbook Part 8 |
| `fig_change_travels.svg` | The seven-step loop after setup, development machine then VM | handbook §6, `03-git-workflow.md` |
| `fig_two_stage_identification.svg` | Stage 1 (either identifier) versus stage 2 (both must agree) | handbook §9, `09-chemical-identification.md`, playbook Part 4 |
| `fig_registry_first.svg` | The registry as a gate: a row needs both keys, name and CAS, to match one registered entry; otherwise it waits on the unregistered list | `09-chemical-identification.md` (the specification), `05-roadmap.md` |
| `fig_module_names.svg` | The sidebar before and after the renames; addresses unchanged | phase SH-1 tutorial, playbook Part 3 |
| `fig_registry_sources.svg` | The Dotmatics export, the registry SDF and the limited list as template specs feeding one registry | `09-registry-sources.md`, phase CR-9 tutorial |
| `fig_every_way_in.svg` | Browser, API, terminal and the export loop all reach the registry through one import module | phase CR-3 tutorial, registry tasks page, playbook |
| `fig_delete_gate.svg` | Deleting a compound with linked rows: refused in the browser and the plain API, unlink-then-delete when forced or from the script | phase CR-6 tutorial, `09-chemical-identification.md`, registry tasks page |
| `fig_auth_ladder.svg` | The three rungs from an open port to single sign-on, one flag, one open health route | `13-authentication.md`, handbook §10 |
| `fig_tracks.svg` | The six tracks of the plan, one per module and the shared spine, each with its next phase | `05-roadmap.md`, handbook §10 |
| `fig_container_lunchbox.svg` | The same image on three platforms; what is mounted in and what comes out | the three setup guides, handbook §3 |
| `fig_setup_flow.svg` | Set up once, then the loop | the three setup guides, handbook §3 |
| `fig_timeline.svg` | The milestones on one line | handbook §1 |
| `fig_requirements_lock.svg` | The wish list, the receipt, and who installs from it | phase 05b tutorial, `backend/README.md` |
| `fig_two_instances.svg` | Production and beta on one server: two folders, two containers, two ports; publish, promote, and the one-way data copy | `14-beta-instance.md`, phase SH-12 tutorial, `01-setup-rhel8.md` §8, handbook §10 |
| `fig_six_blocks.svg` | The route of every change since the beta instance: six blocks in two rows, publish (development machine, mirror, beta folder) and, after the testers agree, promote (development machine, mirror, production folder) | `03-git-workflow.md`, handbook §6 |
| `fig_token_gate.svg` | The token gate (SH-3a): three callers meet one guard in front of every module; a browser with a cookie and a script with a bearer header pass, anyone else gets 401; health, instance and the login routes stay open | `04-phase-tutorials/phase-sh-3a-token-gate.md`, `10-user-playbook.md`, `13-authentication.md` |
| `fig_token_travels.svg` | Where the token lives, how it travels and where it never goes: the owner-only settings file, the container script, the container, the guard; the cookie as a keyed hash, the header for scripts; never in git, logs, errors or the page | `04-phase-tutorials/phase-sh-3a-token-gate.md`, `07-operations.md` |
| `fig_two_tokens.svg` | One token per instance (A11): beta and production side by side, each with its own token in its own settings file and its own people; one token never opens the other door | `04-phase-tutorials/phase-sh-3a-token-gate.md`, `13-authentication.md`, `14-beta-instance.md` |
| `fig_publish_promote.svg` | Three branch stations on one rail — develop, beta, master; publish pushes develop to beta, promotion pushes beta to master by hand; which instance pulls what | phase SH-12 tutorial, `03-git-workflow.md`, `14-beta-instance.md`, handbook §6 |
| `fig_two_doors.svg` | One running application per instance with the service inside; two doors into it, the script and `systemctl`; the boot key underneath (lingering plus an enabled service) | `15-run-stop-status.md`, handbook §8 |
| `fig_instance_label.svg` | One name in the settings file becomes a word and a colour in the page's corner: the chain from `.env.local` to the pill, and the two headers side by side, indigo *Prod* and amber *Beta* | phase SH-13 tutorial, `14-beta-instance.md`, playbook |
| `fig_instance_name.svg` | The three lines of the beta folder's `.env.local` fanning out to the image, container, service unit, monitor log, cron line and address; production's file beside it for contrast | phase SH-12 tutorial, `14-beta-instance.md`, `07-operations.md`, `01-setup-rhel8.md` §8 |
| `fig_source_tags.svg` | Four entries with their source tags, the two readings of a multi-tag filter, the strip of batch counts | phase CR-11 tutorial, `09-registry-sources.md`, registry tasks page |
| `fig_attention_page.svg` | One audit module behind the browser's attention page, the API and the script; the review mark lives on the entry | phase CR-10 tutorial, `09-registry-sources.md`, registry tasks page |

**Two kinds of diagram, and when to use which.** Anything that will change
with the code — the system view, a request's path, the deployment layout, the
entity-relationship diagram, a decision flow — is written inline in the
documents in the diagram language the public host renders natively (fenced
`mermaid` blocks), so a code change and its diagram change are one edit in one
file. The ideas that need *drawing* — a symbol per record type, a row with its
document, the two repositories — are generated SVG here, because they must
look identical everywhere and carry the shared symbols.

The interactive figure — the animated architecture page served at
`/architecture` — is a separate, hand-written file,
[`../architecture-interactive.html`](../architecture-interactive.html),
described in [`02-architecture.md`](../02-architecture.md#interactive-architecture-page).

**Last Updated:** September 22, 2026
