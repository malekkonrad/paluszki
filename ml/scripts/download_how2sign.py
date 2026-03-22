import argparse
import os
import shutil
import subprocess
import sys
import zipfile
import tarfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent / "datasets" / "How2Sign"


DATASETS = {
    "english_translation": {
        "train": {
            "type": "file",
            "filename": "how2sign_train.csv",
            "gdrive_id": "1lq7ksWeD3FzaIwowRbe_BvCmSmOG12-f",
            "target_dir": ROOT / "sentence_level/train/text/en/raw_text",
        },
        "val": {
            "type": "file",
            "filename": "how2sign_val.csv",
            "gdrive_id": "1aBQUClTlZB504JtDISJ0DJlbuYUZCGu3",
            "target_dir": ROOT / "sentence_level/val/text/en/raw_text",
        },
        "test": {
            "type": "file",
            "filename": "how2sign_test.csv",
            "gdrive_id": "1ScxYnEjILZMn22qKjQj8Wyr_F0nha7kG",
            "target_dir": ROOT / "sentence_level/test/text/en/raw_text",
        },
    },
    "english_translation_re-aligned": {
        "train": {
            "type": "file",
            "filename": "how2sign_realigned_train.csv",
            "gdrive_id": "1dUHSoefk9OxKJnHrHPX--I4tpm9QD0ok",
            "target_dir": ROOT / "sentence_level/train/text/en/raw_text/re_aligned",
        },
        "val": {
            "type": "file",
            "filename": "how2sign_realigned_val.csv",
            "gdrive_id": "1Vpag7VPfdTCCJSao8Pz14rlPfekRMggI",
            "target_dir": ROOT / "sentence_level/val/text/en/raw_text/re_aligned",
        },
        "test": {
            "type": "file",
            "filename": "how2sign_realigned_test.csv",
            "gdrive_id": "1AgwBZW26kFHS4CWNMQTCMPGkBPkH3qCu",
            "target_dir": ROOT / "sentence_level/test/text/en/raw_text/re_aligned",
        },
    },
    "rgb_front_clips": {
        "train": {
            "type": "zip",
            "filename": "train_rgb_front_clips.zip",
            "gdrive_id": "1VX7n0jjW0pW3GEdgOks3z8nqE6iI6EnW",
            "target_dir": ROOT / "sentence_level/train/rgb_front",
        },
        "val": {
            "type": "zip",
            "filename": "val_rgb_front_clips.zip",
            "gdrive_id": "1DhLH8tIBn9HsTzUJUfsEOGcP4l9EvOiO",
            "target_dir": ROOT / "sentence_level/val/rgb_front",
        },
        "test": {
            "type": "zip",
            "filename": "test_rgb_front_clips.zip",
            "gdrive_id": "1qTIXFsu8M55HrCiaGv7vZ7GkdB3ubjaG",
            "target_dir": ROOT / "sentence_level/test/rgb_front",
        },
    },
}


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def run(cmd):
    print(">>>", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def download_from_gdrive_wget(file_id: str, output_path: Path):
    """
    Pobieranie dużych plików z Google Drive przez wget.
    Działa lepiej niż gdown dla bardzo dużych archiwów.
    """
    ensure_dir(output_path.parent)

    cookie_file = output_path.parent / "cookies.txt"
    base_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    # 1) pobierz stronę potwierdzenia i wyciągnij token confirm
    cmd_confirm = f"""wget --quiet --save-cookies "{cookie_file}" --keep-session-cookies --no-check-certificate "{base_url}" -O -"""
    result = subprocess.run(
        cmd_confirm,
        shell=True,
        check=True,
        text=True,
        capture_output=True,
    )

    confirm_token = None
    for line in result.stdout.splitlines():
        if "confirm=" in line:
            import re
            m = re.search(r"confirm=([0-9A-Za-z_]+)", line)
            if m:
                confirm_token = m.group(1)
                break

    # 2) właściwy download
    if confirm_token:
        download_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
    else:
        download_url = base_url

    run([
        "wget",
        "--continue",
        "--tries=20",
        "--retry-connrefused",
        "--waitretry=5",
        "--read-timeout=30",
        "--timeout=30",
        "--no-check-certificate",
        "--load-cookies", str(cookie_file),
        download_url,
        "-O", str(output_path),
    ])

    cookie_file.unlink(missing_ok=True)


def download_small_file_with_gdown(file_id: str, output_path: Path):
    """
    Dla małych plików typu CSV gdown jest OK.
    """
    try:
        import gdown
    except ImportError:
        print("Brakuje pakietu gdown. Zainstaluj:")
        print("    pip install gdown")
        sys.exit(1)

    ensure_dir(output_path.parent)
    url = f"https://drive.google.com/uc?id={file_id}"
    print(f"Pobieram {url} -> {output_path}")
    gdown.download(url, str(output_path), quiet=False, fuzzy=True)


def download_file(file_id: str, output_path: Path, entry_type: str):
    if entry_type in {"zip", "tar.gz"}:
        download_from_gdrive_wget(file_id, output_path)
    else:
        download_small_file_with_gdown(file_id, output_path)


def extract_archive(archive_path: Path, target_dir: Path):
    ensure_dir(target_dir)

    if archive_path.suffix == ".zip":
        print(f"Rozpakowuję ZIP: {archive_path} -> {target_dir}")
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(target_dir)

    elif archive_path.suffixes[-2:] == [".tar", ".gz"] or archive_path.name.endswith(".tar.gz"):
        print(f"Rozpakowuję TAR.GZ: {archive_path} -> {target_dir}")
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(target_dir)

    else:
        raise ValueError(f"Nieobsługiwany format archiwum: {archive_path}")


def move_file(src: Path, target_dir: Path):
    ensure_dir(target_dir)
    dst = target_dir / src.name
    print(f"Przenoszę {src} -> {dst}")
    shutil.move(str(src), str(dst))


def handle_entry(entry: dict, download_only: bool = False, keep_archive: bool = False):
    filename = entry["filename"]
    file_id = entry["gdrive_id"]
    target_dir = Path(entry["target_dir"])
    entry_type = entry["type"]

    tmp_dir = Path(".downloads")
    ensure_dir(tmp_dir)

    local_path = tmp_dir / filename

    if not local_path.exists():
        download_file(file_id, local_path, entry_type)
    else:
        print(f"Plik już istnieje, pomijam download: {local_path}")

    if download_only:
        print(f"Pobrano bez dalszego przetwarzania: {local_path}")
        return

    if entry_type == "file":
        move_file(local_path, target_dir)

    elif entry_type in {"zip", "tar.gz"}:
        extract_archive(local_path, target_dir)
        if not keep_archive:
            print(f"Usuwam archiwum: {local_path}")
            local_path.unlink(missing_ok=True)

    else:
        raise ValueError(f"Nieznany typ wpisu: {entry_type}")


def parse_args():
    parser = argparse.ArgumentParser(description="Downloader for How2Sign")
    parser.add_argument(
        "--modality",
        nargs="+",
        required=True,
        choices=DATASETS.keys(),
        help="Które modality pobrać",
    )
    parser.add_argument(
        "--split",
        nargs="+",
        default=["train", "val", "test"],
        choices=["train", "val", "test"],
        help="Które splity pobrać",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Tylko pobierz pliki, bez rozpakowywania / przenoszenia",
    )
    parser.add_argument(
        "--keep-archive",
        action="store_true",
        help="Nie usuwaj archiwów po rozpakowaniu",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    for modality in args.modality:
        print(f"\n### MODALITY: {modality}")
        modality_map = DATASETS[modality]

        for split in args.split:
            if split not in modality_map:
                print(f"Pomijam {modality}/{split} - brak definicji")
                continue

            print(f"\n--- Split: {split}")
            entry = modality_map[split]
            handle_entry(
                entry,
                download_only=args.download_only,
                keep_archive=args.keep_archive,
            )

    print("\nGotowe.")


if __name__ == "__main__":
    main()