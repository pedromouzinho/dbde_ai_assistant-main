#!/usr/bin/env python3
"""
Quick verification tests for security fixes.
Tests the core validation logic without requiring full app dependencies.
"""

def validate_file_content(filename: str, content: bytes) -> tuple[bool, str]:
    """
    Validate file content using magic bytes to detect actual file type.
    Returns (is_valid, error_message or mime_type).
    """
    if not content or len(content) < 4:
        return False, "Ficheiro vazio ou demasiado pequeno"

    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''

    # Define allowed file types with their magic bytes signatures
    ALLOWED_TYPES = {
        'png': [(b'\x89PNG\r\n\x1a\n', 'image/png')],
        'jpg': [(b'\xff\xd8\xff', 'image/jpeg')],
        'jpeg': [(b'\xff\xd8\xff', 'image/jpeg')],
        'gif': [(b'GIF87a', 'image/gif'), (b'GIF89a', 'image/gif')],
        'pdf': [(b'%PDF', 'application/pdf')],
        'csv': [(None, 'text/csv')],
        'tsv': [(None, 'text/tab-separated-values')],
        'txt': [(None, 'text/plain')],
        'xlsx': [(b'PK\x03\x04', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')],
        'xlsb': [(b'PK\x03\x04', 'application/vnd.ms-excel.sheet.binary.macroenabled.12')],
        'xls': [(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1', 'application/vnd.ms-excel')],
        'docx': [(b'PK\x03\x04', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')],
        'pptx': [(b'PK\x03\x04', 'application/vnd.openxmlformats-officedocument.presentationml.presentation')],
        'zip': [(b'PK\x03\x04', 'application/zip')],
    }

    if ext not in ALLOWED_TYPES:
        return False, f"Tipo de ficheiro .{ext} não permitido"

    expected_signatures = ALLOWED_TYPES[ext]

    # For text-based files (CSV, TSV, TXT), skip magic byte validation
    if expected_signatures[0][0] is None:
        # Basic text validation: check if content is mostly printable ASCII/UTF-8
        try:
            sample = content[:2048].decode('utf-8', errors='strict')
            if len(sample) > 0:
                return True, expected_signatures[0][1]
        except UnicodeDecodeError:
            pass
        # Allow if it decodes as latin-1 (common for CSV files)
        try:
            content[:2048].decode('latin-1', errors='strict')
            return True, expected_signatures[0][1]
        except UnicodeDecodeError:
            return False, f"Ficheiro .{ext} não parece ser texto válido"

    # Check magic bytes for binary files
    for magic_bytes, mime_type in expected_signatures:
        if content.startswith(magic_bytes):
            return True, mime_type

    # Build error message
    expected_desc = " ou ".join(sig[1] for sig in expected_signatures if sig[0] is not None)
    return False, f"Conteúdo do ficheiro não corresponde à extensão .{ext} (esperado: {expected_desc})"


def test_file_validation():
    """Test file content validation function."""
    print("Testing file content validation...")

    # Test 1: Valid PNG
    png_content = b'\x89PNG\r\n\x1a\n' + b'test data' * 100
    is_valid, msg = validate_file_content('test.png', png_content)
    assert is_valid, f"PNG validation failed: {msg}"
    assert msg == 'image/png'
    print("✓ Valid PNG detected correctly")

    # Test 2: Valid JPEG
    jpg_content = b'\xff\xd8\xff' + b'test data' * 100
    is_valid, msg = validate_file_content('test.jpg', jpg_content)
    assert is_valid, f"JPEG validation failed: {msg}"
    assert msg == 'image/jpeg'
    print("✓ Valid JPEG detected correctly")

    # Test 3: Valid CSV
    csv_content = b'name,age,city\nJohn,30,NYC\nJane,25,LA'
    is_valid, msg = validate_file_content('test.csv', csv_content)
    assert is_valid, f"CSV validation failed: {msg}"
    assert msg == 'text/csv'
    print("✓ Valid CSV detected correctly")

    # Test 4: Valid PDF
    pdf_content = b'%PDF-1.4' + b'\n' + b'test content' * 100
    is_valid, msg = validate_file_content('document.pdf', pdf_content)
    assert is_valid, f"PDF validation failed: {msg}"
    assert msg == 'application/pdf'
    print("✓ Valid PDF detected correctly")

    # Test 5: Mismatched extension (PNG content with .jpg extension)
    is_valid, msg = validate_file_content('fake.jpg', png_content)
    assert not is_valid, "Should reject mismatched extension"
    assert 'não corresponde' in msg
    print("✓ Mismatched extension rejected correctly")

    # Test 6: Disallowed file type
    exe_content = b'MZ' + b'\x00' * 100
    is_valid, msg = validate_file_content('malware.exe', exe_content)
    assert not is_valid, "Should reject .exe files"
    assert 'não permitido' in msg
    print("✓ Disallowed file type rejected correctly")

    # Test 7: Empty file
    is_valid, msg = validate_file_content('empty.png', b'')
    assert not is_valid, "Should reject empty files"
    assert 'vazio' in msg
    print("✓ Empty file rejected correctly")

    # Test 8: Valid XLSX (ZIP-based format)
    xlsx_content = b'PK\x03\x04' + b'\x00' * 100
    is_valid, msg = validate_file_content('data.xlsx', xlsx_content)
    assert is_valid, f"XLSX validation failed: {msg}"
    print("✓ Valid XLSX detected correctly")

    print("\n✅ All file validation tests passed!")


def test_config_values():
    """Test that configuration values are set correctly."""
    print("\nTesting configuration...")

    import config

    # Test IS_PRODUCTION detection
    print(f"  IS_PRODUCTION: {config.IS_PRODUCTION}")
    print(f"  PROMPT_SHIELD_FAIL_MODE: {config.PROMPT_SHIELD_FAIL_MODE}")

    # Verify fail mode defaults
    if config.IS_PRODUCTION:
        assert config.PROMPT_SHIELD_FAIL_MODE == 'closed', \
            "Prompt Shield should fail-closed in production"
        print("✓ Prompt Shield set to fail-closed (production)")
    else:
        # Default to open in non-production for better dev experience
        assert config.PROMPT_SHIELD_FAIL_MODE in ['open', 'closed'], \
            f"Invalid fail mode: {config.PROMPT_SHIELD_FAIL_MODE}"
        print(f"✓ Prompt Shield fail mode: {config.PROMPT_SHIELD_FAIL_MODE} (non-production)")

    print("✅ Configuration tests passed!")


if __name__ == '__main__':
    test_file_validation()
    test_config_values()
    print("\n" + "="*60)
    print("All security fix tests completed successfully! ✅")
    print("="*60)
