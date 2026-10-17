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
