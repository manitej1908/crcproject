"""
crc/crc_checker.py
------------------
CRC-32 utility module for the Industrial Machine Log Integrity Checker.

This module provides pure, reusable CRC-32 functions that work at the
byte level. CRC-32 is calculated from the exact raw bytes of a file or
data buffer — no parsing, no reconstruction.

CRC-32 is an error-detection mechanism, NOT a cryptographic hash.
It reliably detects accidental corruption or modification at the byte
level, but it is not a secure anti-tampering guarantee against a
determined attacker.
"""

import zlib
import os

# Chunk size used when reading large files to avoid loading
# the entire file into memory at once (8 KB chunks).
CHUNK_SIZE: int = 8192


def calculate_crc32(data: bytes) -> int:
    """
    Calculate CRC-32 checksum from raw bytes.

    Uses Python's built-in zlib.crc32(), which implements the standard
    ISO 3309 / ITU-T V.42 CRC-32 polynomial.

    The result is masked with 0xFFFFFFFF to always return an unsigned
    32-bit integer, regardless of platform.

    Args:
        data: Raw bytes to compute the checksum for.

    Returns:
        Unsigned 32-bit integer CRC-32 value.

    Example:
        >>> calculate_crc32(b"hello")
        907060870
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Expected bytes or bytearray, got {type(data).__name__}")

    return zlib.crc32(data) & 0xFFFFFFFF


def calculate_file_crc32(file_path: str) -> int:
    """
    Calculate CRC-32 checksum of a file by reading it in binary chunks.

    Reads the file in CHUNK_SIZE blocks so that large files are handled
    efficiently without loading the entire content into memory.

    The checksum is updated incrementally across all chunks using
    zlib.crc32(chunk, previous_crc), which is mathematically equivalent
    to computing the CRC of the entire file at once.

    Args:
        file_path: Absolute or relative path to the file.

    Returns:
        Unsigned 32-bit integer CRC-32 value.

    Raises:
        FileNotFoundError: If the file does not exist at the given path.
        OSError: If the file cannot be opened or read.
        ValueError: If the file is empty (zero bytes).

    Example:
        >>> crc = calculate_file_crc32("data/machine_log.csv")
        >>> print(format_crc32(crc))
        'A82F91C4'
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: '{file_path}'")

    if not os.path.isfile(file_path):
        raise OSError(f"Path is not a regular file: '{file_path}'")

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise ValueError(f"File is empty (zero bytes): '{file_path}'")

    crc_value: int = 0  # zlib.crc32 starts from 0

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            crc_value = zlib.crc32(chunk, crc_value)

    return crc_value & 0xFFFFFFFF


def calculate_bytes_crc32(data: bytes) -> int:
    """
    Calculate CRC-32 from a complete in-memory bytes buffer.

    This is a convenience wrapper around calculate_crc32() intended for
    use with uploaded file content (e.g., from FastAPI UploadFile.read()).

    Identical bytes will always produce the same CRC-32 value.
    Any single-byte difference in the input will produce a different result.

    Args:
        data: Complete raw bytes of the file (e.g., from UploadFile.read()).

    Returns:
        Unsigned 32-bit integer CRC-32 value.

    Raises:
        TypeError: If data is not bytes or bytearray.
        ValueError: If data is empty.

    Example:
        >>> calculate_bytes_crc32(b"timestamp,machine_id\\n")
        1234567890
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Expected bytes or bytearray, got {type(data).__name__}")

    if len(data) == 0:
        raise ValueError("Cannot calculate CRC-32 of empty data.")

    return zlib.crc32(data) & 0xFFFFFFFF


def format_crc32(crc_value: int) -> str:
    """
    Format a CRC-32 integer value as an 8-character uppercase hex string.

    The output is always exactly 8 characters, zero-padded on the left
    if the numeric value is small.

    Args:
        crc_value: Unsigned 32-bit integer CRC-32 value.

    Returns:
        8-character uppercase hexadecimal string (zero-padded).

    Raises:
        TypeError: If crc_value is not an integer.
        ValueError: If crc_value is negative or exceeds 0xFFFFFFFF.

    Examples:
        >>> format_crc32(0xA82F91C4)
        'A82F91C4'
        >>> format_crc32(1)
        '00000001'
        >>> format_crc32(0)
        '00000000'
    """
    if not isinstance(crc_value, int):
        raise TypeError(f"Expected int, got {type(crc_value).__name__}")

    if crc_value < 0 or crc_value > 0xFFFFFFFF:
        raise ValueError(
            f"CRC-32 value must be in range [0, 4294967295], got {crc_value}"
        )

    return f"{crc_value:08X}"


def calculate_and_format_crc32(data: bytes) -> str:
    """
    Convenience function: calculate CRC-32 from bytes and return formatted hex.

    Combines calculate_bytes_crc32() and format_crc32() in a single call.

    Args:
        data: Raw bytes to compute the checksum for.

    Returns:
        8-character uppercase hexadecimal CRC-32 string.

    Example:
        >>> calculate_and_format_crc32(b"hello world")
        '0D4A1185'
    """
    crc_int = calculate_bytes_crc32(data)
    return format_crc32(crc_int)
