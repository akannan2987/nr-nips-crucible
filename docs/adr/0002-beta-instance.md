[← README](../../README.md) · [Handbook](../HANDBOOK.md) · [All decisions](README.md)

# ADR 0002 — A beta instance on the same server, on the `beta` branch, promoted by hand

**Status:** proposed 2026-09-21 (decisions B1–B6 recommended in [`14-beta-instance.md`](../14-beta-instance.md#decisions-b1b6); accepted when the owner agrees) · **Date:** 2026-09-21

## Context

The application is to be put in front of end users for testing. There is
one instance on the server and it holds the laboratory's real registry;
testing on it means every trial upload, link, merge or deletion lands in
the data the laboratory trusts. The login, which the testers need, has been
planned but not built, and it is the change most worth rehearsing before it
stands between the laboratory and its data. The `beta` branch exists in
both repositories and is pushed with every publish, but nothing runs it.

## Decision

Run a second, complete instance of the application beside production, on
the same server:

1. **Its own folder, branch, container, image, port and database.** The
   folder is checked out on `beta`; three lines in its `.env.local`
   (`CRUCIBLE_INSTANCE=beta`, `CRUCIBLE_PORT=49161`, HTTPS) tell the same
   `container-py.sh` to name its image and container `crucible-py-beta`.
   The two instances share nothing at run time.
2. **The `beta` branch means the beta instance.** A publish pushes
   `develop` to `develop` and `beta`; production's `master` moves only by
   a deliberate promotion of `beta` once the testers are satisfied.
3. **Data flows one way.** Beta receives a copy of production's latest
   backup on request, through the existing `restore` command; nothing ever
   flows back.
4. **The login arrives on beta first**, as local accounts in full, with
   one account per tester; production adopts it after the test.

## Alternatives considered

- **Test on production with care.** Rejected: one wrong click reaches the
  real registry, and the login cannot be rehearsed on the instance it will
  lock.
- **A second machine.** Preferred in principle and requested from IT;
  rejected for now because it does not exist, and the design moves to it
  unchanged when it does (B1).
- **A second container from the same image and the same branch.** Rejected:
  a rebuild for beta would replace production's image, and there would be
  no way to give the testers a change production does not yet have.
- **A feature flag inside one instance** ("test mode"). Rejected: it
  shares the database, which is the whole problem.
- **Synthetic data on beta instead of a copy.** Rejected as the default:
  testers judge the real registry; the synthetic templates remain
  available for a clean slate.

## Consequences

- One more folder on the server, one more service unit, one more monitor
  line, and one more workflow step (promotion) written into
  [`03-git-workflow.md`](../03-git-workflow.md).
- Every publish is exercised on beta before it can reach production; a
  change that fails there is never promoted.
- `container-py.sh`, `setup-after-clone-py.sh` and the setup guides learn
  an instance name; a machine that never sets one behaves as before, on
  every platform.
- Beta's copy of the data ages until refreshed; the refresh is two
  commands and is documented beside them.
- The login's first users are the testers, not the laboratory.
