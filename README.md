# homebrew-keel

Official Homebrew tap for [keel](https://github.com/berkayturanci/keel) — project-neutral, multi-agent workflow core.

## Installation

```bash
brew tap berkayturanci/keel
brew install keel
```

Or in one command:

```bash
brew install berkayturanci/keel/keel
```

## This formula is generated, not edited here

`Formula/keel.rb` is published from the [keel repository](https://github.com/berkayturanci/keel/blob/main/Formula/keel.rb). **Edit it there.**

A scheduled workflow in this repo pulls that file, resolves its `url`, re-hashes the artifact the way `brew` does, and commits only when the two differ and the digest checks out. Nothing is mirrored blindly: keel 1.16.0 shipped with 1.15.0's checksum and `brew install` refused it ([keel#805](https://github.com/berkayturanci/keel/issues/805)) — a tap that republished whatever it was handed would have copied that faithfully.

Editing the copy here by hand would pass no checks and be overwritten on the next sync. The source repo is where the guards live: the digest is compared against the released artifact on every push, and the release itself refuses to publish a formula that does not hash to its own tarball.

To publish a change immediately instead of waiting for the schedule:

```bash
gh workflow run "Sync formula from keel" --repo berkayturanci/homebrew-keel
```

## Why the tap pulls instead of being pushed to

A workflow's `GITHUB_TOKEN` is scoped to its own repository, so pushing from the keel repo required a personal access token with write access here — a long-lived credential, stored in another repository, needing rotation. Reading a public repository needs no credential at all, and the token that writes this tap is this tap's own. There is no secret to leak.

## Licence

Apache-2.0, matching keel.
