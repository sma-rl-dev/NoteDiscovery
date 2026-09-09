# Tester environment

Baseline source: upstream `v0.31.5` / `fe9f47bc93aae8125f9a6ce36c35d4120da130f2`.

## Deploy, seed, verify, reset

```bash
./tester-env deploy
./tester-env seed
./tester-env verify
./tester-env status
./tester-env logs
./tester-env stop
./tester-env reset
```

The app runs at `http://localhost:8115` by default. `PORT` changes that host
port; `RUN_ID` scopes the container and data volume; `IMAGE_TAG` overrides the
default `tester-env-notediscovery:dev` image tag. No authentication is enabled.

`seed` creates four deterministic Markdown notes: Atlas Launch, Release
Checklist, Search Notes, and Welcome. `verify` checks `/health`, all four note
paths, and their expected source markers. `reset` removes only this tester
environment's Compose container and named volume, not its image.

## Evidence

- `./tester-env deploy` built the upstream Dockerfile from source and received
  `/health` 200 at `http://localhost:8115`.
- A reset followed by deploy returned an empty `/api/notes` list; reset, deploy,
  seed, and verify then recreated and checked the four-note fixture.
- Browser smoke loaded the app without authentication, opened
  `Projects/Atlas-Launch` (Atlas Launch Plan, Maya Chen, release checklist, and
  1/3 tasks), searched `blue lantern` (one Search Notes result), and toggled
  Confirm release window from 1/3 to 2/3 and back.

The overlay uses host networking because this Docker host has no free
user-defined network subnets. It is Linux-only; distinct `PORT` values support
parallel runs.
