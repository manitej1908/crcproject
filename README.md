# Industrial Machine Log Integrity Checker

A FastAPI backend that uses **CRC-32** checksums to verify whether an industrial
machine log CSV file has been modified, corrupted, or tampered with since it was
originally recorded.

---

## Problem Statement

Manufacturing machines generate operational log files continuously. These files
record critical data including temperature readings, vibration levels, operating
states, and fault events.

After a log file leaves the machine — during network transmission, cloud storage,
archiving, or sharing — it may be:

- **Accidentally edited** by an operator
- **Corrupted** during file transfer or storage
- **Truncated** due to a network interruption
- **Deliberately modified** to conceal a fault event
- **Missing records** due to a storage failure
- **Containing injected records** not present in the original

The system must be able to answer the question:

> *"Is the file I have right now byte-for-byte identical to the original file
> that the machine produced?"*

---

## Objective

Implement a simple, transparent file integrity verification system using the
CRC-32 error-detection algorithm. The system:

1. Accepts an original machine log CSV file and computes its CRC-32 checksum.
2. Stores the original CRC as a trusted baseline.
3. Later accepts a "current" version of the file.
4. Computes the current CRC-32 and compares it to the baseline.
5. Returns a clear **VALID** or **MODIFIED_OR_CORRUPTED** verdict.

---

## Features

- **CRC-32 integrity verification** — byte-level, deterministic, fast
- **File registration** — establishes a trusted original baseline
- **File verification** — checks current file against registered baseline
- **Standalone CRC calculation** — compute CRC of any CSV without registering
- **CSV validation** — validates headers, data types, timestamps, and status values
- **Disk integrity check** — detects if the stored original file was altered on disk
- **Registration status check** — query whether a baseline is currently active
- **Swagger UI** — full API documentation at `/docs`
- **No database** — lightweight, runs anywhere with Python installed

---

## Technology Stack

| Component       | Technology             |
|----------------|------------------------|
| Language        | Python 3.11+           |
| Web framework   | FastAPI                |
| ASGI server     | Uvicorn                |
| Data validation | Pydantic v2            |
| CRC algorithm   | Python `zlib.crc32()`  |
| CSV parsing     | Python `csv` (stdlib)  |
| File uploads    | `python-multipart`     |
| Testing         | pytest + httpx         |
| API docs        | Swagger UI (built-in)  |

---

## Project Structure

```
industrial-log-integrity-checker/
│
├── data/
│   └── machine_log.csv         ← Sample industrial machine log (160+ records)
│
├── crc/
│   ├── __init__.py
│   └── crc_checker.py          ← CRC-32 utility functions
│
├── tests/
│   ├── __init__.py
│   └── test_crc.py             ← pytest test suite (unit + integration)
│
├── main.py                     ← FastAPI application (all endpoints)
│
├── requirements.txt            ← Minimal Python dependencies
│
└── README.md                   ← This file
```

---

## How CRC-32 Works

**CRC** stands for **Cyclic Redundancy Check**. CRC-32 is a specific variant that
produces a 32-bit (4-byte) integer checksum.

### The Calculation

```
Input:  Any sequence of bytes
Output: A single 32-bit unsigned integer (0 to 4,294,967,295)
```

The algorithm treats the input bytes as a binary polynomial and divides it by a
fixed generator polynomial (0xEDB88320 in the reflected IEEE 802.3 form).
The remainder of this division is the CRC.

Python makes this trivial:

```python
import zlib

data = b"hello world"
crc = zlib.crc32(data) & 0xFFFFFFFF  # Always unsigned 32-bit
print(f"{crc:08X}")                   # → '0D4A1185'
```

### Why the `& 0xFFFFFFFF` mask?

Python's `zlib.crc32()` can return a negative integer on some platforms.
Masking with `0xFFFFFFFF` forces the result into the standard unsigned 32-bit
range [0, 4,294,967,295], making outputs consistent and portable.

### Chunked File Reading

For large files, the CRC is computed incrementally in 8 KB chunks:

```python
crc = 0
with open(file_path, "rb") as f:
    while chunk := f.read(8192):
        crc = zlib.crc32(chunk, crc)  # Feed previous CRC as seed
crc &= 0xFFFFFFFF
```

This is mathematically equivalent to reading the whole file at once.

### Output Format

The 32-bit integer is formatted as an **8-character uppercase hexadecimal string**,
zero-padded if necessary:

| CRC Integer  | Formatted Output |
|-------------|-----------------|
| 2821109700   | `A82F91C4`       |
| 1            | `00000001`       |
| 0            | `00000000`       |
| 4294967295   | `FFFFFFFF`       |

---

## Why CRC-32?

CRC-32 is widely used in industrial and embedded systems for error detection because:

- **Speed** — Extremely fast to compute, even on resource-constrained hardware.
- **Simplicity** — Single integer output, trivial to store and compare.
- **Determinism** — Same bytes → same CRC. Always. On every platform.
- **Sensitivity** — Any single-bit change in the file produces a different CRC
  with very high probability (~99.9999998%).
- **Standard** — Used in ZIP, PNG, Ethernet frames, SATA, Modbus, and many others.

---

## CRC-32 Limitations

**CRC-32 is NOT a cryptographic hash function.**

| Property                  | CRC-32 | SHA-256 |
|--------------------------|--------|---------|
| Collision resistant       | Weak   | Strong  |
| Pre-image resistant       | No     | Yes     |
| Tamper-proof against attacker | No  | Yes (with HMAC) |
| Speed                     | Very fast | Fast |
| Output size               | 32 bits | 256 bits |
| Industry use              | Error detection | Security |

### What a CRC mismatch tells you:

> "The byte sequence of the current file differs from the registered original
> byte sequence."

### What a CRC mismatch does NOT tell you:

- **Who** changed the file
- **What** specifically changed (which field, which row)
- **Why** the change occurred (accident vs malice)
- **When** the change happened
- **How many** bytes were changed

### Determined Attacker Weakness

A skilled attacker who knows the CRC polynomial can craft a malicious file that
produces the **same CRC as the original** (a CRC collision). Therefore, CRC-32
should NOT be used as a security guarantee against deliberate tampering.

### Recommended Future Upgrade

For stronger tamper detection, replace or supplement CRC-32 with:

```
HMAC-SHA-256(file_bytes, secret_key)
```

This is cryptographically secure and cannot be forged without knowing the secret key.

---

## System Workflow

```
ORIGINAL MACHINE LOG
        │
        ▼
  Read exact file bytes (binary mode "rb")
        │
        ▼
  zlib.crc32() → 32-bit integer → formatted as 8-char hex
        │
        ▼
  Store original CRC in memory (baseline)
        │
        ▼
  Later: receive current file
        │
        ▼
  Read exact file bytes (binary mode "rb")
        │
        ▼
  Calculate current CRC-32
        │
        ▼
  Compare: original_crc == current_crc?
        │
   ┌────┴────┐
   │         │
  YES        NO
   │         │
   ▼         ▼
 VALID   MODIFIED_OR_CORRUPTED
```

---

## Installation

### 1. Clone or download the project

```bash
git clone <repository-url>
cd industrial-log-integrity-checker
```

### 2. Create a virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the FastAPI Server

```bash
uvicorn main:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

---

## Swagger Documentation

Open your browser and navigate to:

```
http://127.0.0.1:8000/docs
```

You will see the interactive Swagger UI with all endpoints documented and testable
directly in your browser.

Alternative ReDoc documentation:
```
http://127.0.0.1:8000/redoc
```

---

## API Endpoint Documentation

### `GET /health`
Returns the health status of the service.

**Response:**
```json
{
  "status": "healthy",
  "service": "Industrial Machine Log Integrity Checker"
}
```

---

### `POST /api/v1/crc/calculate`
Calculates and returns the CRC-32 of an uploaded CSV file.

Does **not** save the file or compare to any baseline.

**Request:** `multipart/form-data`
- `file` — CSV file to checksum

**Response:**
```json
{
  "filename": "machine_log.csv",
  "file_size": 8742,
  "crc32": "A82F91C4"
}
```

**Errors:** `400` (invalid file), `413` (file too large)

---

### `POST /api/v1/logs/register`
Registers an original machine log as the trusted integrity baseline.

Saves the file to `data/machine_log.csv` and stores the CRC-32 in memory.

> ⚠️ The baseline resets when the server restarts.

**Request:** `multipart/form-data`
- `file` — Original machine log CSV file
- `machine_id` — Machine identifier string (e.g., `MACHINE-001`)

**Response (201):**
```json
{
  "message": "Original machine log registered successfully.",
  "filename": "machine_log.csv",
  "machine_id": "MACHINE-001",
  "file_size": 8742,
  "original_crc32": "A82F91C4",
  "registered_at": "2026-09-01 09:00:00 UTC"
}
```

**Errors:** `400` (invalid file/CSV), `413` (file too large), `500` (disk write failure)

---

### `POST /api/v1/logs/verify`
Verifies a machine log CSV against the registered baseline.

**Request:** `multipart/form-data`
- `file` — Current machine log CSV file to verify

**Response — VALID:**
```json
{
  "filename": "machine_log.csv",
  "original_crc32": "A82F91C4",
  "current_crc32": "A82F91C4",
  "is_identical": true,
  "integrity_status": "VALID",
  "message": "File integrity verified. The current file matches the original file."
}
```

**Response — MODIFIED_OR_CORRUPTED:**
```json
{
  "filename": "machine_log.csv",
  "original_crc32": "A82F91C4",
  "current_crc32": "73D4B812",
  "is_identical": false,
  "integrity_status": "MODIFIED_OR_CORRUPTED",
  "message": "Integrity verification failed. The current file differs from the original file. The file may have been edited, corrupted, truncated, or modified during transmission or storage."
}
```

**Errors:** `400` (invalid file), `404` (no baseline registered)

---

### `GET /api/v1/logs/original`
Returns registered baseline metadata and re-checks the stored file on disk.

**Response:**
```json
{
  "message": "Original log metadata retrieved successfully.",
  "machine_id": "MACHINE-001",
  "filename": "machine_log.csv",
  "file_size": 8742,
  "original_crc32": "A82F91C4",
  "registered_at": "2026-09-01 09:00:00 UTC",
  "current_file_crc32": "A82F91C4",
  "original_file_still_intact": true
}
```

**Errors:** `404` (no baseline registered or file deleted from disk)

---

### `GET /api/v1/logs/status`
Returns the current registration status of the baseline.

**Response (registered):**
```json
{
  "registered": true,
  "machine_id": "MACHINE-001",
  "filename": "machine_log.csv",
  "file_size": 8742,
  "original_crc32": "A82F91C4",
  "registered_at": "2026-09-01 09:00:00 UTC"
}
```

**Response (not registered):**
```json
{
  "registered": false,
  "machine_id": null,
  "filename": null,
  "file_size": null,
  "original_crc32": null,
  "registered_at": null
}
```

---

## Testing

Run the full test suite:

```bash
pytest tests/test_crc.py -v
```

Run only CRC unit tests:

```bash
pytest tests/test_crc.py -v -k "crc"
```

Run only API integration tests:

```bash
pytest tests/test_crc.py -v -k "api"
```

Run with a summary report:

```bash
pytest tests/test_crc.py -v --tb=short
```

### What the Tests Verify

| Test Group                          | What It Checks |
|------------------------------------|---------------|
| `TestCalculateCrc32`               | Same data → same CRC; different data → different CRC; single-byte change; empty bytes; range; type errors |
| `TestCalculateBytesCrc32`          | Valid bytes → CRC; empty bytes rejected; non-bytes rejected |
| `TestFormatCrc32`                  | 8 characters; uppercase hex; zero-padded; no prefix; max value; known value; error cases |
| `TestCalculateFileCrc32`           | File CRC matches bytes CRC; modification detected; single-byte change; empty file; non-existent file; chunked large file |
| `TestCalculateAndFormatCrc32`      | Combined function consistency; empty bytes rejected |
| `TestCRCIntegrityDemonstration`    | Temperature change; deleted row; added row; fault code change; truncation; restore |
| `TestAPIEndpoints`                 | All 6 endpoints; valid/invalid requests; CRC consistency across endpoints; registration state |

---

## Demonstration Procedure

This is the step-by-step demonstration procedure for a college viva.

### Step 1 — Start the server

```bash
uvicorn main:app --reload
```

Open: `http://127.0.0.1:8000/docs`

---

### Step 2 — Check health

**GET /health**

Expected:
```json
{ "status": "healthy", "service": "Industrial Machine Log Integrity Checker" }
```

---

### Step 3 — Check status (unregistered)

**GET /api/v1/logs/status**

Expected:
```json
{ "registered": false, ... }
```

---

### Step 4 — Register the original machine log

**POST /api/v1/logs/register**
- Upload: `data/machine_log.csv`
- machine_id: `MACHINE-001`

Expected response:
```json
{
  "message": "Original machine log registered successfully.",
  "machine_id": "MACHINE-001",
  "original_crc32": "XXXXXXXX"   ← note this value
}
```

**Record the `original_crc32` value. This is the trusted baseline.**

---

### Step 5 — Verify the original file (should pass)

**POST /api/v1/logs/verify**
- Upload: the same `data/machine_log.csv`

Expected:
```json
{
  "is_identical": true,
  "integrity_status": "VALID",
  "original_crc32": "XXXXXXXX",
  "current_crc32":  "XXXXXXXX"
}
```

✅ CRCs match → File is intact.

---

### Step 6 — Modify the file (change a temperature value)

Make a copy of `data/machine_log.csv` and change:
```
72.5 → 92.5
```
(Change the temperature in the first data row)

Save as `machine_log_modified.csv`.

**POST /api/v1/logs/verify**
- Upload: `machine_log_modified.csv`

Expected:
```json
{
  "is_identical": false,
  "integrity_status": "MODIFIED_OR_CORRUPTED",
  "original_crc32": "XXXXXXXX",
  "current_crc32":  "YYYYYYYY"   ← different value
}
```

❌ CRCs differ → Modification detected.

---

### Step 7 — Delete a row and verify

Open a copy of the original CSV. Delete the OVERHEAT row:
```
2026-09-01 09:15:00,MACHINE-001,97.3,0.79,ON,101,OVERHEAT
```

Save as `machine_log_deleted_row.csv`.

**POST /api/v1/logs/verify**
- Upload: `machine_log_deleted_row.csv`

Expected: `MODIFIED_OR_CORRUPTED`

❌ A deleted record changes the byte sequence → CRC changes.

---

### Step 8 — Add a row and verify

Append a new row to a copy of the original:
```
2026-09-02 08:00:00,MACHINE-001,99.9,1.50,ON,301,SENSOR_FAULT
```

Save as `machine_log_added_row.csv`.

**POST /api/v1/logs/verify**
- Upload: `machine_log_added_row.csv`

Expected: `MODIFIED_OR_CORRUPTED`

❌ An injected record changes the byte sequence → CRC changes.

---

### Step 9 — Change a fault code and verify

In a copy, change:
```
101,OVERHEAT → 999,UNKNOWN
```

Save as `machine_log_changed_fault.csv`.

**POST /api/v1/logs/verify**

Expected: `MODIFIED_OR_CORRUPTED`

❌ Changed fault data detected.

---

### Step 10 — Restore original and verify

**POST /api/v1/logs/verify**
- Upload: the original `data/machine_log.csv`

Expected: `VALID`

✅ Restoring the original bytes restores the CRC → File is intact again.

---

## Explaining Results in a Viva

### Q: Why does changing one temperature value change the CRC?

**A:** CRC-32 is computed from the raw bytes of the file. Changing `72.5` to `92.5`
changes two characters (`7` → `9`), which changes two bytes in the file. Even a
one-byte change affects the CRC with near-certainty (probability of collision is
approximately 1 in 4 billion).

### Q: Why can't we tell exactly what changed from the CRC mismatch?

**A:** CRC-32 produces a single 32-bit summary of the entire file. It tells us
the files are different at the byte level, but not which bytes changed, how many
changed, or why. It is a checksum, not a diff tool.

### Q: Is CRC-32 secure against deliberate tampering?

**A:** No. A determined attacker who knows the CRC algorithm can craft a malicious
file that produces the same CRC as the original (called a collision). CRC-32 is
designed for accidental error detection, not adversarial security. For
tamper-resistant systems, use HMAC-SHA-256.

### Q: Why use raw bytes instead of parsing the CSV first?

**A:** If we parsed the CSV and reconstructed it, the output might differ from the
original due to whitespace differences, quote handling, or line ending variations.
Computing CRC on the raw bytes ensures we detect any byte-level change, including
invisible ones like a trailing space or a different line ending (CRLF vs LF).

---

## Future Improvements

| Feature | Description |
|---------|-------------|
| HMAC-SHA-256 | Replace/supplement CRC-32 with a cryptographic MAC for tamper-proof verification |
| SQLite baseline storage | Persist the baseline across server restarts |
| Multiple machine support | Register and verify logs for multiple machine IDs |
| Diff report | After mismatch, show which rows differ (using a separate diff tool) |
| Audit log | Track all register/verify operations with timestamps |
| File hash history | Store a history of all CRC values for trend analysis |
| Frontend UI | Add a simple web interface (React or plain HTML) |
| Scheduled verification | Automatically re-verify stored files on a schedule |
| REST authentication | Protect endpoints with API keys or JWT tokens |

---

## License

MIT — Free for educational and demonstration use.
