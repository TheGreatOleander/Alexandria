"""
Alexandria — Persistence

Two persistence backends:

LedgerStore — simple JSON file persistence.
  Saves the event ledger as a JSON array.
  Restores by replaying events in timestamp order.

GitLedger — git as canonical substrate.
  Each event is a commit to an append-only JSONL ledger file.
  Equilibrium snapshots are tagged commits.
  Fork domains are git branches.
  The git log IS the audit trail.

Usage:

    # Simple file persistence
    store = LedgerStore()
    store.save(kernel, "ledger.json")
    store.restore(kernel2, "ledger.json")

    # Git-backed ledger
    gl = GitLedger("/path/to/repo").init()
    gl.append(event)
    gl.append_equilibrium(kernel, label="end-of-day")
    events = gl.load()
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from alexandria.kernel import TemporalKernel, Event


class LedgerStore:
    """
    Simple JSON file persistence for the event ledger.

    Saves as a JSON array of event dicts.
    Restores by replaying events in timestamp order.
    """

    def save(self, kernel: "TemporalKernel", path: str):
        """Save kernel's ledger to a JSON file."""
        with open(path, "w") as f:
            json.dump([e.to_dict() for e in kernel.ledger], f, indent=2)

    def load(self, path: str) -> List["Event"]:
        """Load events from a JSON file."""
        from alexandria.kernel import Event
        with open(path) as f:
            return [Event.from_dict(r) for r in json.load(f)]

    def restore(self, kernel: "TemporalKernel", path: str) -> "TemporalKernel":
        """
        Restore kernel state by replaying events from a JSON file.
        Clears existing state before restoring.
        """
        events = self.load(path)
        kernel.ledger = []
        kernel.state = {}
        for event in sorted(events, key=lambda e: e.ts):
            kernel.ledger.append(event)
            kernel.state.update(event.payload)
        return kernel


class GitLedger:
    """
    Git as canonical substrate for the event ledger.

    Each event appended to the ledger becomes a git commit.
    The git log is the audit trail. Forks are git branches.
    Equilibrium snapshots are tagged commits with full reports.

    The repo path must be writable. Git must be available on PATH.
    """

    def __init__(
        self,
        repo_path: str,
        author: str = "Alexandria <kernel@alexandria>",
    ):
        self.repo_path = repo_path
        self.author = author
        self._ledger_file = os.path.join(repo_path, "LEDGER.jsonl")

    def init(self) -> "GitLedger":
        """Initialise the git repository if it doesn't exist."""
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            os.makedirs(self.repo_path, exist_ok=True)
            self._git("init")
            self._git(
                "commit", "--allow-empty", "-m", "Alexandria: genesis block"
            )
        return self

    def append(self, event: "Event", message: Optional[str] = None) -> str:
        """
        Append an event to the JSONL ledger and commit.
        Returns the resulting git commit hash.
        """
        with open(self._ledger_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
        self._git("add", self._ledger_file)
        msg = message or (
            f"event:{event.domain}:{event.id[:8]} [{event.source}]"
        )
        self._git("commit", "-m", msg, f"--author={self.author}")
        return self._git("rev-parse", "HEAD").strip()

    def append_equilibrium(
        self,
        kernel: "TemporalKernel",
        label: str,
    ) -> str:
        """
        Commit a full equilibrium report as a tagged snapshot.
        Returns the commit hash.
        """
        report = kernel.equilibrium_report()
        tag_file = os.path.join(self.repo_path, f"EQUILIBRIUM_{label}.json")
        with open(tag_file, "w") as f:
            json.dump(report, f, indent=2)
        self._git("add", tag_file)
        self._git(
            "commit",
            "-m",
            f"equilibrium:{label} tension={report.get('tension', '?')}",
        )
        commit = self._git("rev-parse", "HEAD").strip()
        self._git("tag", f"equilibrium/{label}", commit)
        return commit

    def load(self) -> List["Event"]:
        """Load all events from the JSONL ledger file."""
        from alexandria.kernel import Event
        if not os.path.exists(self._ledger_file):
            return []
        events = []
        with open(self._ledger_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(Event.from_dict(json.loads(line)))
        return events

    def fork_domain(self, domain_name: str) -> "GitLedger":
        """Create a new git branch for a domain fork."""
        self._git("checkout", "-b", f"domain/{domain_name}")
        return GitLedger(self.repo_path, self.author)

    def log(self) -> List[str]:
        """Return the git log as a list of one-line strings."""
        return self._git("log", "--oneline").strip().splitlines()

    def restore_kernel(
        self, kernel: "TemporalKernel"
    ) -> "TemporalKernel":
        """
        Restore kernel state from the git ledger.
        Replays events in timestamp order.
        """
        events = self.load()
        kernel.ledger = []
        kernel.state = {}
        for event in sorted(events, key=lambda e: e.ts):
            kernel.ledger.append(event)
            kernel.state.update(event.payload)
        return kernel

    def _git(self, *args) -> str:
        result = subprocess.run(
            ["git", "-C", self.repo_path, *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
