from __future__ import annotations

import os
from typing import Callable

from fastapi import HTTPException


_TEXT_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".log",
    ".svg",
}


def _decode_text_sample(sample: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            return sample.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(400, "Ficheiro de texto com encoding inválido ou conteúdo corrompido.")


def _looks_like_text(sample: bytes) -> bool:
    if not sample:
        return False
    if b"\x00" in sample:
        return False
    text = _decode_text_sample(sample)
    significant = [ch for ch in text if not ch.isspace()]
    if not significant:
        return True
    printable = sum(1 for ch in significant if ch.isprintable())
    return (printable / len(significant)) >= 0.85


def _is_webp(sample: bytes) -> bool:
    return len(sample) >= 12 and sample.startswith(b"RIFF") and sample[8:12] == b"WEBP"


_BINARY_VALIDATORS: dict[str, Callable[[bytes], bool]] = {
    ".xlsx": lambda sample: sample.startswith(b"PK\x03\x04"),
    ".xlsb": lambda sample: sample.startswith(b"PK\x03\x04"),
    ".xls": lambda sample: sample.startswith(b"\xd0\xcf\x11\xe0"),
    ".pdf": lambda sample: sample.startswith(b"%PDF"),
    ".png": lambda sample: sample.startswith(b"\x89PNG"),
    ".jpg": lambda sample: sample.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda sample: sample.startswith(b"\xff\xd8\xff"),
    ".gif": lambda sample: sample.startswith(b"GIF87a") or sample.startswith(b"GIF89a"),
    ".webp": _is_webp,
    ".bmp": lambda sample: sample.startswith(b"BM"),
    ".pptx": lambda sample: sample.startswith(b"PK\x03\x04"),
}


def validate_upload_content(filename: str, content: bytes) -> None:
    sample = content[:8192]
    if not sample:
        raise HTTPException(400, "Ficheiro vazio.")

    ext = os.path.splitext((filename or "").lower())[1]
    if not ext:
        return

    validator = _BINARY_VALIDATORS.get(ext)
    if validator is not None:
        if not validator(sample):
            raise HTTPException(
                400,
                f"Conteúdo do ficheiro não corresponde à extensão '{ext}'. Verifica o ficheiro e tenta novamente.",
            )
        return

    if ext not in _TEXT_EXTENSIONS:
        return

    if not _looks_like_text(sample):
        raise HTTPException(
            400,
            f"Conteúdo do ficheiro não parece compatível com a extensão '{ext}'.",
        )

    if ext == ".svg":
        text = _decode_text_sample(sample).lower()
        if "<svg" not in text:
            raise HTTPException(400, "O ficheiro .svg não contém markup SVG válido.")
