[← README](../../README.md) · [Handbook](../HANDBOOK.md) · [All decisions](README.md)

# ADR 0001 — Authentication as a ladder, with single sign-on as the destination

**Status:** accepted 2026-09-08 (decisions A1–A8 agreed as recommended; log in [`13-authentication.md`](../13-authentication.md#decision-log)) · **Date:** 2026-09-08

## Context

Every route under `/api/*` answers anyone who can reach the port. That was
deliberate while the system was built on one trusted internal network, and
it blocks every later control: roles, an audit trail that says who, rate
limits. The organisation's requirement is that the final login is **single
sign-on** through its identity provider. Single sign-on needs an
application registration from another team, with a lead time we do not
control, so "wait for SSO" means an open port for an unknown number of
weeks.

## Decision

Add authentication as three rungs behind one feature flag, `AUTH_MODE`,
each rung secure on its own and each keeping what the rung below gave:

1. **A token gate** (`token`): one shared secret, now, needing nothing from
   anyone; tokens remain for scripts and service accounts forever.
2. **Local accounts** (`local`): usernames, Argon2-hashed passwords, a
   signed session cookie, three roles — in full only if the registration
   is slow, otherwise just one break-glass admin.
3. **Single sign-on** (`sso`): OpenID Connect, authorization code flow with
   PKCE, roles from a group claim, the same session cookie. The
   destination.

One dependency function, `require_user`, guards every route and produces
the same identity shape on every rung, so nothing above it changes when
the flag moves. One open route, `/api/health`, keeps the monitor working.
The API contract is unchanged; the only new answer is 401.

## Alternatives considered

- **Single sign-on directly, nothing before it.** Rejected: leaves the port
  open for the registration's lead time, and gives scripts no way in
  (they have no browser) — tokens would be needed anyway.
- **An authenticating reverse proxy.** Deferred: a second web server, which
  the roadmap deliberately avoids; becomes attractive only if the
  organisation offers a managed gateway, in which case rung 3 shrinks to
  trusting the gateway's header.
- **Local accounts as the destination.** Rejected: Crucible would hold
  passwords the organisation would rather it did not, and leavers would
  keep access until someone noticed.
- **A network allow-list alone.** Rejected: on a corporate network many
  people share one address; useful only as a second layer.

## Consequences

- Three phases in the shared spine, SH-3a, SH-3b, SH-3c, in that order;
  SH-4 (roles everywhere, audit, rate limits) waits on b or c.
- The registration request to the identity team is made **now**, in
  parallel with SH-3a, because it is the long pole.
- Three new dependencies over the ladder (`argon2-cffi`, `itsdangerous`,
  `authlib`), each entering `requirements.lock` through the usual lock
  step, each justified in the plan.
- HTTPS becomes mandatory whenever the flag is not `off`; the setup guides'
  `.env.local` step gains the mode and the token.
- Secrets never enter git: the token, the session secret and the client
  secret live in `.env.local` and its off-repository backup only.
