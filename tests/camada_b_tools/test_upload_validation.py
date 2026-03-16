import pytest
from fastapi import HTTPException

from upload_validation import validate_upload_content


def test_validate_upload_content_accepts_known_binary_types():
    validate_upload_content("image.png", b"\x89PNG\r\n\x1a\nresto")
    validate_upload_content("document.pdf", b"%PDF-1.7 resto")
    validate_upload_content("slides.pptx", b"PK\x03\x04resto")


def test_validate_upload_content_rejects_mismatched_binary_types():
    with pytest.raises(HTTPException) as exc:
        validate_upload_content("fake.jpg", b"\x89PNG\r\n\x1a\nresto")
    assert exc.value.status_code == 400
    assert "não corresponde" in str(exc.value.detail)


def test_validate_upload_content_accepts_text_and_svg():
    validate_upload_content("table.csv", b"name,age\nAna,30\n")
    validate_upload_content("diagram.svg", b"<?xml version='1.0'?><svg viewBox='0 0 10 10'></svg>")


def test_validate_upload_content_rejects_binary_disguised_as_text():
    with pytest.raises(HTTPException) as exc:
        validate_upload_content("table.csv", b"\x00\x01\x02\x03\x04\x05")
    assert exc.value.status_code == 400


def test_validate_upload_content_rejects_invalid_svg():
    with pytest.raises(HTTPException) as exc:
        validate_upload_content("diagram.svg", b"<html>not svg</html>")
    assert exc.value.status_code == 400
    assert "svg" in str(exc.value.detail).lower()
