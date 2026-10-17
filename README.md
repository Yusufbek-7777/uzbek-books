# uzbek-books

Ўзбек тилидаги китоблар, дарсликлар, луғатлар ва матн корпусларини бир жойга йиғиш лойиҳаси.

## Таркиби

| Йўл | Нима |
|---|---|
| [`sources/uzbek_sources.yaml`](sources/uzbek_sources.yaml) | Барча ўзбекча манбалар каталоги (58 та): реестрдаги 40 та ва қўшимча топилган 18 та |
| [`sources/23_til_adabiyotlar_va_matnlar_reestri.txt`](sources/23_til_adabiyotlar_va_matnlar_reestri.txt) | Асл реестр файли |
| [`scripts/fetch_sources.py`](scripts/fetch_sources.py) | Каталогни кўриш, ҳаволаларни текшириш ва манбаларни юклаб олиш |

Ҳар бир манбанинг `access` майдони уни қандай йиғиш мумкинлигини кўрсатади:

- **bulk** (27 та): скрипт бутун манбани ёки унинг ўзбекча қисмини юклайди. Булар Hugging Face датасетлари, GitHub репозиторийлари, Википедия дамплари ва UD трибанклари.
- **direct** (7 та): фақат каталогда кўрсатилган алоҳида PDF файллар юкланади.
- **browse** (24 та): портал ёки кутубхона. Улар автоматик юкланмайди, чунки китобларнинг кўпчилиги муаллифлик ҳуқуқи остида ёки сайтда оммавий юклаш имконияти йўқ.

## Ишлатиш

```bash
pip install -r requirements.txt

python3 scripts/fetch_sources.py list                 # каталог
python3 scripts/fetch_sources.py check                # ҳаволаларни текшириш -> reports/link_check.csv
python3 scripts/fetch_sources.py fetch --dry-run      # нима юкланишини кўриш
python3 scripts/fetch_sources.py fetch                # очиқ манбаларни data/ га юклаш
python3 scripts/fetch_sources.py fetch --only UZ-TXT-05 UZ-ADD-01

# Рухсат талаб қиладиган (CulturaX, OSCAR, FLORES+) ва жуда катта (FineWeb-2, MADLAD-400, STT) манбалар:
HF_TOKEN=hf_... python3 scripts/fetch_sources.py fetch --include-gated --include-large
```

Юкланган маълумотлар `data/<манба-id>/` папкасига тушади ва git'га қўшилмайди.

## Каталогга манба қўшиш

`sources/uzbek_sources.yaml` га янги ёзув қўшинг: `id` (`UZ-ADD-NN`), `name`, `group`, `format`, `access`, `origin`, `urls`, ва юклаб олиш мумкин бўлса `fetch`.

## Модель ўргатиш учун матн тайёрлаш

```bash
# Тозалаш, лотинга ўгириш, апострофни бир хил қилиш, такрорларни олиб ташлаш -> JSONL
python3 scripts/normalize.py data/UZ-TXT-05 data/UZ-TXT-03 -o corpus/uz.jsonl
python3 scripts/normalize.py kitob.txt --script keep --apostrophe official -o corpus/kitob.jsonl

# Токенизаторларни ўзбекча намунада солиштириш (бир сўзга неча токен)
pip install transformers sentencepiece
python3 scripts/tokenizer_fertility.py corpus/uz.jsonl \
    google/gemma-3-4b-it Qwen/Qwen3-4B meta-llama/Llama-3.2-3B --train-sp 32000
```

`--apostrophe ascii` (асосий) oʻ, gʻ ва тутуқ белгисининг ҳамма вариантини `'` га келтиради. `official` эса расмий `ʻ` ва `ʼ` белгиларини қўяди.
