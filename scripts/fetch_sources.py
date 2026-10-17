#!/usr/bin/env python3
"""Ўзбек тилидаги манбаларни каталог (sources/uzbek_sources.yaml) асосида йиғиш.

Буйруқлар:
  list    каталогни жадвал кўринишида чиқаради
  check   ҳар бир ҳаволани текширади ва reports/link_check.csv га ёзади
  fetch   bulk/direct манбаларни data/ папкасига юклайди

Мисоллар:
  python3 scripts/fetch_sources.py list
  python3 scripts/fetch_sources.py check
  python3 scripts/fetch_sources.py fetch --dry-run
  python3 scripts/fetch_sources.py fetch --only UZ-TXT-05 UZ-ADD-01
  HF_TOKEN=... python3 scripts/fetch_sources.py fetch --include-gated --include-large
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "sources" / "uzbek_sources.yaml"
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
USER_AGENT = "uzbek-books-collector/0.1 (+https://github.com/Yusufbek-7777/uzbek-books)"
IA_EXTENSIONS = (".pdf", ".txt", ".djvu", ".epub")


def load_catalog():
    with open(CATALOG, encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]


def cmd_list(sources, args):
    for s in sources:
        n_fetch = len(s.get("fetch", []))
        print(f"{s['id']:<10} {s['access']:<7} {s['origin']:<9} fetch={n_fetch:<2} {s['name']}")
    by_access = {}
    for s in sources:
        by_access[s["access"]] = by_access.get(s["access"], 0) + 1
    print(f"\nЖами: {len(sources)} та манба; " + ", ".join(f"{k}={v}" for k, v in sorted(by_access.items())))


def probe(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        # Баъзи сайтлар HEAD ни рад этади; GET билан қайта уриниб кўрамиз.
        if e.code in (403, 405):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.status, r.geturl()
            except urllib.error.HTTPError as e2:
                return e2.code, ""
            except Exception as e2:
                return f"error: {e2}", ""
        return e.code, ""
    except Exception as e:
        return f"error: {e}", ""


def cmd_check(sources, args):
    rows = []
    for s in sources:
        for url in s.get("urls", []):
            rows.append((s["id"], "page", url))
        for f in s.get("fetch", []):
            if f["type"] == "url":
                rows.append((s["id"], "file", f["url"]))
            elif f["type"] == "git":
                rows.append((s["id"], "git", f["url"]))
            elif f["type"] == "hf":
                rows.append((s["id"], "hf", f"https://huggingface.co/api/datasets/{f['repo']}"))
            elif f["type"] == "ia":
                rows.append((s["id"], "ia", f"https://archive.org/metadata/{f['item']}"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda r: probe(r[2]), rows))
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / "link_check.csv"
    ok = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "kind", "url", "status", "final_url"])
        for (sid, kind, url), (status, final) in zip(rows, results):
            w.writerow([sid, kind, url, status, final])
            if isinstance(status, int) and status < 400:
                ok += 1
            else:
                print(f"  {sid} {kind} {status} {url}")
    print(f"\n{ok}/{len(rows)} та ҳавола ишлаяпти. Ҳисобот: {out.relative_to(ROOT)}")


def run(cmd, dry):
    print("  $ " + " ".join(cmd))
    if dry:
        return True
    return subprocess.run(cmd).returncode == 0


def fetch_hf(spec, dest, dry):
    print(f"  hf {spec['repo']} patterns={spec.get('patterns', ['*'])}")
    if dry:
        return True
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=spec["repo"],
        repo_type="dataset",
        local_dir=dest / spec["repo"].replace("/", "__"),
        allow_patterns=spec.get("patterns"),
        token=os.environ.get("HF_TOKEN"),
    )
    return True


def fetch_git(spec, dest, dry):
    target = dest / spec["url"].rstrip("/").split("/")[-1]
    if target.exists():
        return run(["git", "-C", str(target), "pull", "--ff-only"], dry)
    return run(["git", "clone", "--depth", "1", spec["url"], str(target)], dry)


def download(url, target, dry):
    print(f"  url {url} -> {target.relative_to(ROOT)}")
    if dry or target.exists():
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(target)
    return True


def fetch_url(spec, dest, dry):
    name = urllib.parse.unquote(urllib.parse.urlparse(spec["url"]).path.rstrip("/").split("/")[-1]) or "index"
    return download(spec["url"], dest / name, dry)


def fetch_ia(spec, dest, dry):
    item = spec["item"]
    print(f"  ia {item}")
    if dry:
        return True
    req = urllib.request.Request(f"https://archive.org/metadata/{item}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        meta = json.load(r)
    for f in meta.get("files", []):
        if f["name"].lower().endswith(IA_EXTENSIONS):
            url = f"https://archive.org/download/{item}/{urllib.parse.quote(f['name'])}"
            download(url, dest / item / f["name"], dry)
    return True


FETCHERS = {"hf": fetch_hf, "git": fetch_git, "url": fetch_url, "ia": fetch_ia}


def cmd_fetch(sources, args):
    failures = []
    for s in sources:
        if args.only and s["id"] not in args.only:
            continue
        if s["access"] == "browse":
            continue
        for spec in s.get("fetch", []):
            if spec.get("gated") and not args.include_gated:
                print(f"{s['id']}: {spec.get('repo')} ўтказиб юборилди (gated, --include-gated ва HF_TOKEN керак)")
                continue
            if spec.get("large") and not args.include_large:
                print(f"{s['id']}: {spec.get('repo')} ўтказиб юборилди (катта ҳажм, --include-large керак)")
                continue
            print(f"{s['id']}: {s['name']}")
            dest = DATA / s["id"]
            try:
                if not FETCHERS[spec["type"]](spec, dest, args.dry_run):
                    failures.append((s["id"], spec, "command failed"))
            except Exception as e:
                print(f"  ХАТО: {e}")
                failures.append((s["id"], spec, str(e)))
    if failures:
        print(f"\n{len(failures)} та юклаш муваффақиятсиз:")
        for sid, spec, err in failures:
            print(f"  {sid} {spec.get('repo') or spec.get('url') or spec.get('item')}: {err}")
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("check")
    f = sub.add_parser("fetch")
    f.add_argument("--only", nargs="+", metavar="ID", help="фақат шу манбалар")
    f.add_argument("--dry-run", action="store_true", help="юкламасдан нима қилинишини кўрсатади")
    f.add_argument("--include-gated", action="store_true", help="HF да рухсат талаб қиладиган датасетлар")
    f.add_argument("--include-large", action="store_true", help="юзлаб ГБлик манбалар (FineWeb-2, MADLAD, STT)")
    args = p.parse_args()
    {"list": cmd_list, "check": cmd_check, "fetch": cmd_fetch}[args.cmd](load_catalog(), args)


if __name__ == "__main__":
    main()
