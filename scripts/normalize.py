#!/usr/bin/env python3
"""Ўзбекча матнни модель ўргатиш учун тозалаш ва бир хил кўринишга келтириш.

Қиладиган ишлари:
  - Unicode NFC, кўринмас белгилар (soft hyphen, zero-width) ни олиб ташлаш
  - сатр охирида «-» билан бўлинган сўзларни бирлаштириш
  - фақат рақамдан иборат сатрларни (саҳифа рақамлари) ташлаб юбориш
  - сўз ичидаги аралаш алифбо (кирилл сўзда лотин «о» ва ҳ.к.) ни тузатиш
  - кирилл -> лотин транслитерацияси (--script latin, асосий)
  - oʻ/gʻ ва тутуқ белгисининг барча вариантларини битта белгига келтириш
  - бир хил ҳужжатларни такрорламаслик

Кириш: .txt, .jsonl ("text" майдони), .conllu ("# text =" сатрлари), .parquet ("text" устуни).
Чиқиш: JSONL, ҳар сатрда {"source": ..., "text": ...}.

Мисол:
  python3 scripts/normalize.py data/UZ-TXT-03 -o corpus/ud.jsonl
  python3 scripts/normalize.py kitob.txt --apostrophe official -o corpus/kitob.jsonl
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

# oʻ, gʻ ва тутуқ белгиси учун учрайдиган барча апостроф вариантлари.
APOSTROPHES = "'‘’`´ʻʼʹ′"
APOS_RE = re.compile(f"[{re.escape(APOSTROPHES)}]")
INVISIBLE_RE = re.compile("[­​‌‍⁠﻿]")
HYPHEN_BREAK_RE = re.compile(r"(\w)[-‐‑]\n[ \t]*(\w)")
PAGE_NUMBER_RE = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$", re.M)
SPACES_RE = re.compile(r"[ \t ]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")
WORD_RE = re.compile(r"\w+", re.U)
# Репозиторийлардаги хизмат файллари (матн эмас).
SKIP_NAMES = ("LICENSE", "README", "CONTRIBUTING", "CHANGELOG", "REQUIREMENTS")

CYR = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяўқғҳ")
LAT = set("abcdefghijklmnopqrstuvwxyz")
# Бир хил кўринадиган ҳарфлар (лотин -> кирилл).
HOMOGLYPHS = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у",
              "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "H": "Н", "O": "О",
              "P": "Р", "C": "С", "T": "Т", "X": "Х"}
HOMOGLYPHS_REV = {v: k for k, v in HOMOGLYPHS.items()}

CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sh", "ъ": "ʼ", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "oʻ", "қ": "q", "ғ": "gʻ", "ҳ": "h",
}
VOWELS = set("аеёиоуўэюяaeiou")


def fix_mixed_script(word):
    """Кирилл сўз ичидаги лотин ҳарфни (ёки аксинча) тўғрилайди."""
    letters = [ch.lower() for ch in word if ch.isalpha()]
    n_cyr = sum(ch in CYR for ch in letters)
    n_lat = sum(ch in LAT for ch in letters)
    if n_cyr and n_lat:
        if n_cyr >= n_lat:
            return "".join(HOMOGLYPHS.get(ch, ch) for ch in word)
        return "".join(HOMOGLYPHS_REV.get(ch, ch) for ch in word)
    return word


def cyr_to_lat(text):
    out = []
    for i, ch in enumerate(text):
        low = ch.lower()
        if low not in CYR2LAT:
            out.append(ch)
            continue
        prev = text[i - 1].lower() if i else ""
        if low == "е":
            # Сўз бошида ва унлидан кейин «е» -> «ye».
            lat = "ye" if (not prev.isalpha() or prev in VOWELS or prev in "ъь") else "e"
        else:
            lat = CYR2LAT[low]
        if ch.isupper() and lat:
            nxt = text[i + 1] if i + 1 < len(text) else ""
            lat = lat.upper() if (nxt.isupper() or (prev.isupper() and prev.isalpha())) else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


def normalize(text, script="latin", apostrophe="ascii"):
    text = unicodedata.normalize("NFC", text)
    text = INVISIBLE_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = PAGE_NUMBER_RE.sub("", text)
    text = WORD_RE.sub(lambda m: fix_mixed_script(m.group(0)), text)
    if script == "latin":
        text = cyr_to_lat(text)
    if apostrophe == "ascii":
        text = APOS_RE.sub("'", text)
    else:
        # Расмий имло: oʻ/gʻ учун ʻ (U+02BB), тутуқ белгиси учун ʼ (U+02BC).
        text = re.sub(f"(\\w)[{re.escape(APOSTROPHES)}]",
                      lambda m: m.group(1) + ("ʻ" if m.group(1) in "oOgG" else "ʼ"), text)
    text = SPACES_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return BLANK_LINES_RE.sub("\n\n", text).strip()


def read_documents(path):
    suffix = path.suffix.lower()
    if suffix == ".txt":
        yield path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".jsonl":
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line).get("text", "")
    elif suffix == ".conllu":
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("# text = "):
                    yield line[len("# text = "):].rstrip("\n")
    elif suffix == ".parquet":
        import pyarrow.parquet as pq

        table = pq.read_table(path, columns=["text"])
        yield from table.column("text").to_pylist()


def iter_files(inputs):
    for inp in inputs:
        p = Path(inp)
        files = sorted(p.rglob("*")) if p.is_dir() else [p]
        for f in files:
            if f.name.upper().startswith(SKIP_NAMES) or ".git" in f.parts:
                continue
            if f.is_file() and f.suffix.lower() in (".txt", ".jsonl", ".conllu", ".parquet"):
                yield f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="файл ёки папкалар")
    ap.add_argument("-o", "--output", required=True, help="чиқиш JSONL файли")
    ap.add_argument("--script", choices=["latin", "keep"], default="latin", help="кирилл матнни лотинга ўгириш")
    ap.add_argument("--apostrophe", choices=["ascii", "official"], default="ascii",
                    help="ascii: ҳаммаси ' ; official: oʻ/gʻ учун ʻ, тутуқ учун ʼ")
    ap.add_argument("--min-chars", type=int, default=20, help="бундан қисқа ҳужжатлар ташланади")
    args = ap.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    kept = dropped_short = dropped_dup = 0
    with open(out, "w", encoding="utf-8") as w:
        for path in iter_files(args.inputs):
            for doc in read_documents(path):
                text = normalize(doc or "", args.script, args.apostrophe)
                if len(text) < args.min_chars:
                    dropped_short += 1
                    continue
                digest = hashlib.sha1(text.encode()).digest()
                if digest in seen:
                    dropped_dup += 1
                    continue
                seen.add(digest)
                w.write(json.dumps({"source": str(path), "text": text}, ensure_ascii=False) + "\n")
                kept += 1
    print(f"{kept} та ҳужжат ёзилди -> {out} (қисқа: {dropped_short}, такрор: {dropped_dup})", file=sys.stderr)


if __name__ == "__main__":
    main()
