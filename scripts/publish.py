#!/usr/bin/env python3
"""Publish a RuhGenesis universe from a GitHub issue to universes.json.

The issue body must contain a ```universe fenced JSON block with:
  {id, name, seed, author, createdAt, stats{planets, life, maxTech, simYears}}
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REGISTRY = "universes.json"
MAX_UNIVERSES = 500


def gh_api(*args):
    r = subprocess.run(
        ["gh", "api", *args], capture_output=True, text=True, check=True
    )
    return r.stdout


def main():
    issue_number = os.environ["ISSUE_NUMBER"]
    body = os.environ.get("ISSUE_BODY", "")

    def fail(msg):
        gh_api(f"repos/Ruhvibes/ruhgenesis-universes/issues/{issue_number}/comments",
               "-f", f"body=❌ Universe rejected: {msg}")
        gh_api(f"repos/Ruhvibes/ruhgenesis-universes/issues/{issue_number}",
               "-X", "PATCH", "-f", "state=closed")
        print("REJECTED:", msg)
        sys.exit(0)

    m = re.search(r"```universe\s*(\{.*?\})\s*```", body, re.DOTALL)
    if not m:
        fail("no ```universe JSON block found in issue body.")
    try:
        u = json.loads(m.group(1))
    except json.JSONDecodeError:
        fail("universe JSON is not valid JSON.")

    for field in ("id", "name", "seed"):
        if not u.get(field) or not isinstance(u.get(field), str):
            fail(f"missing or invalid field: {field}")
    if len(u["name"]) > 60 or len(u["seed"]) > 200 or len(u["id"]) > 64:
        fail("field too long.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", u["id"]):
        fail("id must be alphanumeric.")

    try:
        with open(REGISTRY) as f:
            reg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        reg = {"universes": []}

    universes = reg.get("universes", [])
    if any(x.get("id") == u["id"] for x in universes):
        fail("this universe is already published.")

    entry = {
        "id": u["id"],
        "name": u["name"][:60],
        "seed": u["seed"][:200],
        "author": str(u.get("author", "anonymous"))[:40],
        "createdAt": u.get("createdAt") or datetime.now(timezone.utc).isoformat(),
        "stats": u.get("stats", {}) if isinstance(u.get("stats"), dict) else {},
    }
    universes.insert(0, entry)
    reg["universes"] = universes[:MAX_UNIVERSES]
    reg["updated"] = datetime.now(timezone.utc).isoformat()

    with open(REGISTRY, "w") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
        f.write("\n")

    subprocess.run(["git", "config", "user.name", "ruhgenesis-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "bot@ruhvibes.local"], check=True)
    subprocess.run(["git", "add", REGISTRY], check=True)
    subprocess.run(["git", "commit", "-m", f"Publish universe {entry['id']}"], check=True)
    subprocess.run(["git", "push"], check=True)

    gh_api(f"repos/Ruhvibes/ruhgenesis-universes/issues/{issue_number}/comments",
           "-f", "body=🚀 Universe **{}** published! It now appears in Explore Global Universe.".format(entry["name"]))
    gh_api(f"repos/Ruhvibes/ruhgenesis-universes/issues/{issue_number}",
           "-X", "PATCH", "-f", "state=closed")
    print("PUBLISHED:", entry["id"])


if __name__ == "__main__":
    main()
