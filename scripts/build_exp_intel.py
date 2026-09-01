#!/usr/bin/env python3
"""Fetch per-task public exploit intel: ARVO-Meta fix commits + OSV advisories.

Pipeline (P1 of the user-task score plan; any-means-assisted mode):

1. For every user task in metadata.json with an ``arvo_<N>`` entry name, fetch
   ``n132/ARVO-Meta`` meta JSON (fix commit, repo, crash report thread).
   Results cached under ``--cache-dir``; re-runs skip existing files.
2. Query OSV (api.osv.dev) by every commit hash we can associate with the
   task: the fix commit, plus the vulnerable-side revision parsed from the
   first ``diff -r <vuln> -r <fix>`` header of the local ``patch.diff``
   (hg-style projects). OSV answers with CVE/GHSA advisories whose affected
   git ranges contain that commit.
3. nofuzz tasks already carry their CVE in the entry name -> direct
   ``/v1/vulns/<id>`` lookup.
4. Emit ``osv_hits.json`` (per entry: advisories with summary/references/
   severity/fixed versions) and print coverage stats.

Everything is offline-consumable afterwards: the JSON is what gets merged into
the per-task CLAUDE.md by ``build_fixdiff_claude_md.py`` (v2 intel section).

Usage:
  python3 scripts/build_exp_intel.py [--cache-dir evol_loop/1/exp_intel/cache]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
META_URL = "https://raw.githubusercontent.com/n132/ARVO-Meta/main/archive_data/meta/{}.json"
OSV_QUERY = "https://api.osv.dev/v1/query"
OSV_VULN = "https://api.osv.dev/v1/vulns/{}"


def http_json(url: str, payload: dict | None = None, timeout: int = 30) -> tuple[int, object]:
    if payload is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:  # noqa: BLE001 - network flakiness -> (0, str)
        return 0, str(e)


def arvo_id(entry_name: str) -> str | None:
    m = re.search(r"arvo_(\d+)$", entry_name)
    return m.group(1) if m else None


def cve_of(entry_name: str) -> str | None:
    m = re.search(r"(CVE-\d{4}-\d{4,})", entry_name)
    return m.group(1) if m else None


def vuln_rev_from_patch(patch_path: Path) -> str | None:
    """First hg-style ``diff -r <vuln> -r <fix>`` revision in patch.diff."""
    if not patch_path.is_file():
        return None
    head = patch_path.read_text(errors="replace")[:400]
    m = re.search(r"diff -r ([0-9a-f]{6,40}) -r [0-9a-f]{6,40}", head)
    return m.group(1) if m else None


def slim_vuln(v: dict) -> dict:
    keep = {}
    for k in ("id", "summary", "details", "aliases", "related", "severity",
              "references", "affected", "published", "modified", "database_specific"):
        if k in v:
            keep[k] = v[k]
    if isinstance(keep.get("details"), str) and len(keep["details"]) > 1200:
        keep["details"] = keep["details"][:1200] + " ..."
    refs = keep.get("references") or []
    keep["references"] = [r.get("url") for r in refs if isinstance(r, dict) and r.get("url")][:15]
    return keep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", type=Path, default=REPO_ROOT / "src/cybergym/task/metadata.json")
    ap.add_argument("--task-data", type=Path, default=REPO_ROOT / "data/tasks/user")
    ap.add_argument("--cache-dir", type=Path, default=REPO_ROOT / "evol_loop/1/exp_intel/cache")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evol_loop/1/exp_intel/osv_hits.json")
    ap.add_argument("--fetch-workers", type=int, default=8)
    ap.add_argument("--osv-workers", type=int, default=4)
    args = ap.parse_args()

    meta = json.loads(args.metadata.read_text())
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    jobs = []  # (entry_name, arvo_id or None, cve or None)
    for e in meta:
        jobs.append((e["entry_name"], arvo_id(e["entry_name"]), cve_of(e["entry_name"])))

    # ── 1. fetch ARVO-Meta jsons (cached) ──────────────────────────────
    todo = [aid for _, aid, _ in jobs if aid]
    fetched = 0

    def fetch_one(aid: str) -> None:
        dst = args.cache_dir / f"{aid}.json"
        if dst.is_file():
            return
        code, body = http_json(META_URL.format(aid))
        if code == 200 and isinstance(body, dict) and body.get("fix_commit"):
            dst.write_text(json.dumps(body))
        else:
            dst.write_text(json.dumps({"error": code or body}))

    with ThreadPoolExecutor(args.fetch_workers) as ex:
        for _ in ex.map(fetch_one, todo):
            fetched += 1
            if fetched % 50 == 0:
                print(f"  meta fetched {fetched}/{len(todo)}", file=sys.stderr)

    fix_commits: dict[str, str] = {}
    meta_ok = meta_missing = 0
    for entry, aid, _ in jobs:
        if not aid:
            continue
        f = args.cache_dir / f"{aid}.json"
        if not f.is_file():
            meta_missing += 1
            continue
        d = json.loads(f.read_text())
        if d.get("fix_commit"):
            fix_commits[entry] = d["fix_commit"]
            meta_ok += 1
        else:
            meta_missing += 1

    # ── 2/3. OSV queries ────────────────────────────────────────────────
    hits: dict[str, list[dict]] = {}
    queries: list[tuple[str, dict]] = []  # (entry, osv payload)

    for entry, aid, cve in jobs:
        if cve:
            queries.append((entry, {"__direct_id__": cve}))
        fc = fix_commits.get(entry)
        if fc:
            queries.append((entry, {"commit": fc}))
            vr = vuln_rev_from_patch(args.task_data / entry / "patch.diff")
            if vr and vr != fc:
                queries.append((entry, {"commit": vr}))

    done = 0

    def osv_one(item: tuple[str, dict]) -> tuple[str, list[dict]]:
        entry, payload = item
        if "__direct_id__" in payload:
            code, body = http_json(OSV_VULN.format(payload["__direct_id__"]))
            vulns = [body] if code == 200 and isinstance(body, dict) and body.get("id") else []
        else:
            code, body = http_json(OSV_QUERY, payload)
            vulns = body.get("vulns", []) if isinstance(body, dict) else []
        return entry, [slim_vuln(v) for v in vulns]

    with ThreadPoolExecutor(args.osv_workers) as ex:
        for entry, vulns in ex.map(osv_one, queries):
            done += 1
            if done % 50 == 0:
                print(f"  osv queried {done}/{len(queries)}", file=sys.stderr)
            if vulns:
                seen = {v["id"] for v in hits.get(entry, [])}
                hits.setdefault(entry, []).extend(v for v in vulns if v["id"] not in seen)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(hits, indent=1))

    n = len(jobs)
    cve_named = sum(1 for _, _, c in jobs if c)
    with_cve = sum(1 for e in jobs if cve_of(e[0]) or any(
        v["id"].startswith("CVE") or any(a.startswith("CVE") for a in v.get("aliases", []))
        for v in hits.get(e[0], [])))
    print(f"tasks={n}")
    print(f"arvo meta: ok={meta_ok} missing={meta_missing} (42 oss-fuzz_* new-tracker ids expected missing)")
    print(f"osv queries={len(queries)} tasks-with-advisory={len(hits)} ({100*len(hits)/n:.1f}%)")
    print(f"tasks-with-CVE={with_cve} ({100*with_cve/n:.1f}%) incl. {cve_named} nofuzz-named")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
