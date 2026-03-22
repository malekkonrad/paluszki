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

Przykład pobrania danych validacyjnych xd:

`uv run scripts/download_how2sign.py --modality rgb_front_clips --split val` - dane (pliki .mp4)

`uv run scripts/download_how2sign.py --modality english_translation_re-aligned --split val` - dokładne napisy co tam jest (.csv)



## Uruchamienie treningu: 

`uv run -m src.main`


Dla prawdziwego splitu train/val używamy:

`uv run -m src.main --config configs/train_val.yaml`

## Inferencja

Po treningu możesz użyć zapisanego checkpointu:

`uv run -m src.infer --checkpoint artifacts/best_model.pt --video datasets/How2Sign/sentence_level/val/rgb_front/raw_videos/-d5dN54tH2E_0-1-rgb_front.mp4`

Domyślnie inferencja nie pobiera pretrained wag ResNet z internetu.
Jeśli chcesz je wymusić:

`uv run -m src.infer --checkpoint artifacts/best_model.pt --video <sciezka_do_wideo> --use-pretrained-backbone`
