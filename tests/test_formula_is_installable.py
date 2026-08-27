"""What `brew install` will actually do, run here first.

This repository is the copy `brew` downloads. Until now it had three files and
no test of any kind: a formula, a README, and the workflow that overwrites the
formula on a schedule. Nothing checked the result, so the first signal that a
sync had written something unusable was somebody's failed install.

The source repository is well guarded and that is not the same thing. Its
guards run on pull requests against a file that is *copied* here; this file is
written by a scheduled job, with no pull request and no review, and it is the
one users fetch.

Two kinds of check:

* **Offline** — the formula's shape, and the internal agreements a reader would
  assume hold: every downloadable thing carries a digest, and the version in the
  url is the version the test line asserts. Cheap, hermetic, and they catch a
  formula that is malformed rather than merely stale.
* **Online** — download every url and hash it, exactly as `brew` does. Opt-in
  via ``KEEL_TAP_CHECK_EXTERNAL=1`` so the offline suite stays hermetic, and
  wired into CI where the value of looking is highest.

Note the plural. The sync job verifies the *top-level* digest only, while this
formula also vendors PyYAML as a `resource` with its own url and sha256 — a
second thing `brew` downloads and checksums. keel#787 is what a broken vendored
dependency looks like from a user's side: every command dying on `import yaml`
before printing anything. Nothing checked that pair until now.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unittest
import urllib.error
import urllib.request
from pathlib import Path

FORMULA = Path(__file__).resolve().parent.parent / "Formula" / "keel.rb"
ONLINE = os.environ.get("KEEL_TAP_CHECK_EXTERNAL") == "1"

#: Every ``url``/``sha256`` pair in the file, in order: the formula's own first,
#: then one per ``resource`` block. Both are things `brew` fetches and checksums,
#: and a wrong digest fails the install identically either way.
PAIR = re.compile(r'url "(?P<url>https://[^"]+)"\s*\n\s*sha256 "(?P<sha>[0-9a-f]{64})"')


def pairs() -> list[tuple[str, str]]:
    return [(m.group("url"), m.group("sha")) for m in PAIR.finditer(FORMULA.read_text(encoding="utf-8"))]


class TheFormulaIsWellFormed(unittest.TestCase):
    """Offline. These would pass on a stale formula — they catch a broken one."""

    def setUp(self):
        self.text = FORMULA.read_text(encoding="utf-8")

    def test_the_file_was_read(self):
        """Vacuity: an empty or missing formula would satisfy several checks."""
        self.assertTrue(self.text.strip(), "the formula is empty")
        self.assertIn("class Keel < Formula", self.text)

    def test_every_downloadable_thing_carries_a_digest(self):
        """A `url` with no `sha256` under it installs whatever it is served.

        Asserted by counting rather than by matching pairs: the pair regex would
        silently skip a url whose digest is missing, and report the rest as fine.
        """
        urls = re.findall(r'^\s*url "https://', self.text, re.M)
        self.assertEqual(
            len(urls),
            len(pairs()),
            "a url in this formula has no sha256 immediately after it",
        )

    def test_there_is_at_least_the_formula_and_its_vendored_resource(self):
        """Guards the online cases from passing by finding nothing to check."""
        self.assertGreaterEqual(len(pairs()), 2)

    def test_a_version_named_in_the_test_block_matches_the_url(self):
        """Conditional: only if the block pins a version at all.

        The first draft asserted this unconditionally and failed — this formula's
        `test do` checks that the binary prints "keel", not which keel. That is a
        legitimate choice, and a test that demands otherwise is inventing a rule
        rather than guarding one. The sibling tap's formula does pin a version,
        and there the agreement is worth holding.
        """
        url_version = re.search(r"/tags/v(\d+\.\d+\.\d+)\.tar\.gz", self.text)
        self.assertIsNotNone(url_version, "no versioned source url")
        block = re.search(r"  test do\n(.*?)\n  end", self.text, re.S)
        self.assertIsNotNone(block, "the formula has no test block")
        pinned = re.search(r"\d+\.\d+\.\d+", block.group(1))
        if pinned is None:
            self.skipTest("the test block does not pin a version")
        self.assertEqual(
            pinned.group(0),
            url_version.group(1),
            "the test block asserts a different version than the url downloads",
        )


@unittest.skipUnless(ONLINE, "set KEEL_TAP_CHECK_EXTERNAL=1 to fetch the artifacts")
class EveryArtifactHashesToItsDeclaredDigest(unittest.TestCase):
    """Online. This is `brew install`'s own check, run before a user runs it."""

    def test_the_tap_is_serving_the_current_release(self):
        """The failure users actually notice: `brew upgrade` finds nothing new.

        This is the outcome of every sync refusal — keel#981 was a day of the tap
        serving a release behind, one failure email per hour, while the packages
        themselves were fine.

        Run right after the sync job in CI, so a brief lag between an upstream tag
        and the next sync is not what this catches. What it catches is a sync that
        ran and did not move.
        """
        url_version = re.search(
            r"/tags/v(\d+\.\d+\.\d+)\.tar\.gz", FORMULA.read_text(encoding="utf-8")
        )
        self.assertIsNotNone(url_version, "no versioned source url")
        try:
            request = urllib.request.Request(
                "https://api.github.com/repos/berkayturanci/keel/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                latest = json.load(response)["tag_name"]
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise self.skipTest(f"cannot reach the releases API: {exc}") from exc
        self.assertEqual(
            f"v{url_version.group(1)}",
            latest,
            "the tap is not serving the current release; `brew upgrade` sees nothing new",
        )

    def test_every_url_resolves_and_hashes_to_its_digest(self):
        checked = 0
        for url, declared in pairs():
            with self.subTest(url=url):
                try:
                    with urllib.request.urlopen(url, timeout=90) as response:
                        payload = response.read(80 * 1024 * 1024)
                except urllib.error.HTTPError as exc:
                    if exc.code == 404:
                        self.fail(f"the formula points at {url}, which does not exist")
                    raise self.skipTest(f"cannot fetch {url}: {exc}") from exc
                except (urllib.error.URLError, OSError) as exc:
                    raise self.skipTest(f"cannot fetch {url}: {exc}") from exc
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(),
                    declared,
                    f"brew install would refuse: {url} is not the file this digest describes",
                )
                checked += 1
        self.assertGreaterEqual(checked, 2, "nothing was actually downloaded")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
