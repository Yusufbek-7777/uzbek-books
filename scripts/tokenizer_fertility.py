#!/usr/bin/env python3
"""Токенизаторларни ўзбекча матнда солиштириш (fertility = бир сўзга ўртача токен).

Fertility қанча кам бўлса, модель шу тилда шунча кам токен сарфлайди.
Ўзбекча учун яхши натижа ~1.3–1.6, умумий моделларда одатда 2.5 дан юқори.

Токенизатор қуйидагича берилади:
  google/gemma-3-4b-it      Hugging Face модели (transformers керак; ёпиқ моделлар учун HF_TOKEN)
  path/to/uz.model          SentencePiece модели
  --train-sp 32000          намунанинг ўзида SentencePiece ўргатиб, у билан ҳам солиштиради

Мисол:
  python3 scripts/tokenizer_fertility.py corpus/sample.jsonl \\
      google/gemma-3-4b-it Qwen/Qwen3-4B meta-llama/Llama-3.2-3B --train-sp 32000
"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

WORD_RE = re.compile(r"\w+(?:['ʻʼ]\w+)*", re.U)


def load_texts(paths, limit):
    texts, chars = [], 0
    for p in paths:
        p = Path(p)
        with open(p, encoding="utf-8") as f:
            if p.suffix == ".jsonl":
                lines = (json.loads(line)["text"] for line in f if line.strip())
            else:
                lines = (line.rstrip("\n") for line in f if line.strip())
            for t in lines:
                texts.append(t)
                chars += len(t)
                if limit and chars >= limit:
                    return texts
    return texts


def hf_encoder(name):
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(name)
    return lambda t: len(tok.encode(t, add_special_tokens=False)), len(tok)


def sp_encoder(model_path):
    import sentencepiece as spm

    sp = spm.SentencePieceProcessor(model_file=str(model_path))
    return lambda t: len(sp.encode(t)), sp.get_piece_size()


def train_sp(texts, vocab_size, out_dir):
    import sentencepiece as spm

    corpus = Path(out_dir) / "sample.txt"
    corpus.write_text("\n".join(texts), encoding="utf-8")
    prefix = Path(out_dir) / f"uz_sp{vocab_size}"
    spm.SentencePieceTrainer.train(
        input=str(corpus), model_prefix=str(prefix), vocab_size=vocab_size,
        model_type="unigram", character_coverage=0.9999, hard_vocab_limit=False,
        minloglevel=2,
    )
    return prefix.with_suffix(".model")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sample", help="намуна: .jsonl (\"text\" майдони) ёки .txt")
    ap.add_argument("tokenizers", nargs="*", help="HF модел номлари ёки .model файллари")
    ap.add_argument("--train-sp", type=int, metavar="VOCAB", help="намунада SentencePiece ўргатиш")
    ap.add_argument("--limit-chars", type=int, default=5_000_000, help="намунадан олинадиган белгилар сони")
    args = ap.parse_args()

    texts = load_texts([args.sample], args.limit_chars)
    words = sum(len(WORD_RE.findall(t)) for t in texts)
    chars = sum(len(t) for t in texts)
    print(f"Намуна: {len(texts)} ҳужжат, {words} сўз, {chars} белги\n", file=sys.stderr)

    encoders = []
    for name in args.tokenizers:
        try:
            enc = sp_encoder(name) if name.endswith(".model") else hf_encoder(name)
            encoders.append((name, *enc))
        except Exception as e:
            print(f"{name}: юклаб бўлмади ({e})", file=sys.stderr)
    tmp = tempfile.TemporaryDirectory()
    if args.train_sp:
        # Эслатма: ўзи ўрганган матнда ўлчангани учун натижа бироз оптимистик чиқади.
        model = train_sp(texts, args.train_sp, tmp.name)
        encoders.append((f"SentencePiece-{args.train_sp} (шу намунада)", *sp_encoder(model)))

    print(f"{'токенизатор':<45} {'луғат':>8} {'токен':>10} {'токен/сўз':>10} {'белги/токен':>12}")
    for name, count, vocab in encoders:
        tokens = sum(count(t) for t in texts)
        print(f"{name:<45} {vocab:>8} {tokens:>10} {tokens / words:>10.2f} {chars / tokens:>12.2f}")


if __name__ == "__main__":
    main()
