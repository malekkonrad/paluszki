# ML

## Używamy uv

### Pobranie
[Link do pobrania](https://docs.astral.sh/uv/getting-started/installation/)


### Korzystanie

`uv run python_file.py`

`uv add package_name`

automatycznie tworzy .venv 


## Dataset How2sign

Znalazłem inny dataset, chyba lepszy - w dużo większy (290Gb zbiór treningowy od przodu xd)

[Link do datasetu](https://how2sign.github.io/#download)


### Skrypt do pobierania:

`uv run scripts/download_how2sign.py --modality rgb_front_clips --split val` - dane (pliki .mp4)

`uv run scripts/download_how2sign.py --modality english_translation_re-aligned --split val` - dokładne napisy co tam jest (.csv)
