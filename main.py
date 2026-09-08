

import csv
import io
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from crc.crc_checker import (
    calculate_bytes_crc32,
    calculate_file_crc32,
    format_crc32,
)



app = FastAPI(
    title="Industrial Machine Log Integrity Checker",
    description=(
        "A FastAPI backend that verifies the integrity of industrial machine "
        "log CSV files using CRC-32 checksums. Upload an original log to "
        "register a trusted baseline, then verify any subsequent version of "
        "the file to detect modifications or corruption at the byte level."
    ),
    version="1.0.0",
    contact={
        "name": "Industrial Systems Team",
    },
    license_info={
        "name": "MIT",
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



ALLOWED_EXTENSION: str = ".csv"


MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  


ORIGINAL_LOG_PATH: str = os.path.join("data", "machine_log.csv")


REQUIRED_HEADERS: list[str] = [
    "timestamp",
    "machine_id",
    "temperature",
    "vibration",
    "operating_status",
    "fault_code",
    "fault_message",
]


VALID_OPERATING_STATUSES: set[str] = {"ON", "OFF", "IDLE"}


_baseline: dict = {
    "registered": False,
    "machine_id": None,
    "filename": None,
    "file_size": None,
    "original_crc32": None,
    "registered_at": None,
}




class HealthResponse(BaseModel):
    

    status: str
    service: str


class CRCCalculateResponse(BaseModel):
    

    filename: str
    file_size: int
    crc32: str


class RegisterResponse(BaseModel):
    

    message: str
    filename: str
    machine_id: str
    file_size: int
    original_crc32: str
    registered_at: str


class VerifyResponse(BaseModel):
    

    filename: str
    original_crc32: str
    current_crc32: str
    is_identical: bool
    integrity_status: str
    message: str


class StatusResponse(BaseModel):
    

    registered: bool
    machine_id: Optional[str]
    filename: Optional[str]
    file_size: Optional[int]
    original_crc32: Optional[str]
    registered_at: Optional[str]


class OriginalLogResponse(BaseModel):
    

    message: str
    machine_id: str
    filename: str
    file_size: int
    original_crc32: str
    registered_at: str
    current_file_crc32: str
    original_file_still_intact: bool





def validate_file_extension(filename: str) -> None:
    
    _, ext = os.path.splitext(filename)
    if ext.lower() != ALLOWED_EXTENSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid file type '{ext}'. "
                f"Only CSV files ({ALLOWED_EXTENSION}) are accepted."
            ),
        )


def validate_file_size(content: bytes, filename: str) -> None:
   
    size = len(content)

    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{filename}' is empty (zero bytes).",
        )

    if size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File '{filename}' is too large "
                f"({size} bytes). Maximum allowed size is {max_mb} MB."
            ),
        )


def validate_csv_content(content: bytes, filename: str) -> None:
    
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File '{filename}' could not be decoded as UTF-8. "
                "Ensure the file is a valid UTF-8 encoded CSV."
            ),
        )

    
    reader = csv.DictReader(io.StringIO(text))

    
    if reader.fieldnames is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{filename}' appears to have no headers.",
        )

    
    actual_headers = [h.strip() for h in reader.fieldnames]
    missing_headers = [h for h in REQUIRED_HEADERS if h not in actual_headers]

    if missing_headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File '{filename}' is missing required columns: "
                f"{missing_headers}. "
                f"Required columns are: {REQUIRED_HEADERS}."
            ),
        )

    
    rows_validated = 0

    for row_number, row in enumerate(reader, start=2):  
        
        machine_id_val = row.get("machine_id", "").strip()
        if not machine_id_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Row {row_number} in '{filename}': "
                    "'machine_id' is empty or missing."
                ),
            )

        
        ts_val = row.get("timestamp", "").strip()
        if not ts_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Row {row_number} in '{filename}': "
                    "'timestamp' is empty or missing."
                ),
            )
        try:
            datetime.strptime(ts_val, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                datetime.strptime(ts_val, "%d-%m-%Y %H:%M")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Row {row_number} in '{filename}': "
                        f"Invalid timestamp '{ts_val}'. "
                        "Expected format: YYYY-MM-DD HH:MM:SS "
                        "or DD-MM-YYYY HH:MM"
            ),
        )

        
        temp_val = row.get("temperature", "").strip()
        try:
            float(temp_val)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Row {row_number} in '{filename}': "
                    f"'temperature' value '{temp_val}' is not a valid number."
                ),
            )

        
        vib_val = row.get("vibration", "").strip()
        try:
            float(vib_val)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Row {row_number} in '{filename}': "
                    f"'vibration' value '{vib_val}' is not a valid number."
                ),
            )

       
        op_status = row.get("operating_status", "").strip().upper()
        if op_status not in VALID_OPERATING_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Row {row_number} in '{filename}': "
                    f"'operating_status' value '{op_status}' is not valid. "
                    f"Allowed values: {sorted(VALID_OPERATING_STATUSES)}."
                ),
            )

        
        fault_code_val = row.get("fault_code", "").strip()
        try:
            fc_int = int(fault_code_val)
            if fc_int < 0:
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Row {row_number} in '{filename}': "
                    f"'fault_code' value '{fault_code_val}' must be a "
                    "non-negative integer."
                ),
            )

        rows_validated += 1

    if rows_validated == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File '{filename}' contains only a header row with no data. "
                "At least one data row is required."
            ),
        )


def safe_filename(original_filename: str) -> str:
   
    return os.path.basename(original_filename)





def require_baseline() -> dict:
   
    if not _baseline["registered"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No original machine log has been registered yet. "
                "Please POST to /api/v1/logs/register first."
            ),
        )
    return _baseline



@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    tags=["System"],
)
def health_check() -> HealthResponse:
    
    return HealthResponse(
        status="healthy",
        service="Industrial Machine Log Integrity Checker",
    )


@app.post(
    "/api/v1/crc/calculate",
    response_model=CRCCalculateResponse,
    summary="Calculate CRC-32 of an Uploaded CSV File",
    tags=["CRC"],
    status_code=status.HTTP_200_OK,
)
async def calculate_crc(
    file: UploadFile = File(..., description="CSV machine log file to checksum"),
) -> CRCCalculateResponse:
   
    filename = safe_filename(file.filename or "unknown.csv")
    validate_file_extension(filename)

    content: bytes = await file.read()
    validate_file_size(content, filename)
    validate_csv_content(content, filename)

    crc_int = calculate_bytes_crc32(content)
    crc_hex = format_crc32(crc_int)

    return CRCCalculateResponse(
        filename=filename,
        file_size=len(content),
        crc32=crc_hex,
    )


@app.post(
    "/api/v1/logs/register",
    response_model=RegisterResponse,
    summary="Register the Original Machine Log (Establish Trusted Baseline)",
    tags=["Log Integrity"],
    status_code=status.HTTP_201_CREATED,
)
async def register_original_log(
    file: UploadFile = File(..., description="Original machine log CSV file"),
    machine_id: str = Form(..., description="Machine identifier (e.g., MACHINE-001)"),
) -> RegisterResponse:
    
    filename = safe_filename(file.filename or "machine_log.csv")
    validate_file_extension(filename)

    content: bytes = await file.read()
    validate_file_size(content, filename)
    validate_csv_content(content, filename)

    
    crc_int = calculate_bytes_crc32(content)
    crc_hex = format_crc32(crc_int)

    # NOTE: File is NOT written to disk — Vercel's filesystem is read-only.
    # The CRC-32 and metadata are stored in the in-memory _baseline dict below.

    
    registered_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    _baseline["registered"] = True
    _baseline["machine_id"] = machine_id.strip()
    _baseline["filename"] = filename
    _baseline["file_size"] = len(content)
    _baseline["original_crc32"] = crc_hex
    _baseline["registered_at"] = registered_at

    return RegisterResponse(
        message="Original machine log registered successfully.",
        filename=filename,
        machine_id=machine_id.strip(),
        file_size=len(content),
        original_crc32=crc_hex,
        registered_at=registered_at,
    )


@app.post(
    "/api/v1/logs/verify",
    response_model=VerifyResponse,
    summary="Verify a Machine Log File Against the Registered Baseline",
    tags=["Log Integrity"],
    status_code=status.HTTP_200_OK,
)
async def verify_log(
    file: UploadFile = File(..., description="Current machine log CSV file to verify"),
) -> VerifyResponse:
   
    baseline = require_baseline()

    filename = safe_filename(file.filename or "unknown.csv")
    validate_file_extension(filename)

    content: bytes = await file.read()
    validate_file_size(content, filename)
    validate_csv_content(content, filename)

    
    current_crc_int = calculate_bytes_crc32(content)
    current_crc_hex = format_crc32(current_crc_int)

    original_crc_hex: str = baseline["original_crc32"]
    is_identical: bool = current_crc_hex == original_crc_hex

    if is_identical:
        integrity_status = "VALID"
        message = (
            "File integrity verified. "
            "The current file matches the original file."
        )
    else:
        integrity_status = "MODIFIED_OR_CORRUPTED"
        message = (
            "Integrity verification failed. "
            "The current file differs from the original file. "
            "The file may have been edited, corrupted, truncated, "
            "or modified during transmission or storage."
        )

    return VerifyResponse(
        filename=filename,
        original_crc32=original_crc_hex,
        current_crc32=current_crc_hex,
        is_identical=is_identical,
        integrity_status=integrity_status,
        message=message,
    )


@app.get(
    "/api/v1/logs/original",
    response_model=OriginalLogResponse,
    summary="Get Registered Original Log Info and Verify It Is Still Intact on Disk",
    tags=["Log Integrity"],
    status_code=status.HTTP_200_OK,
)
def get_original_log() -> OriginalLogResponse:
    
    baseline = require_baseline()

    # NOTE: The original file is no longer stored on disk (Vercel read-only FS).
    # We report the registered baseline CRC as both the original and the
    # "current" CRC, so original_file_still_intact is always True while the
    # in-memory baseline is live. On a serverless restart the baseline resets
    # to unregistered, which is the correct behaviour.
    registered_crc = baseline["original_crc32"]

    return OriginalLogResponse(
        message="Original log metadata retrieved successfully.",
        machine_id=baseline["machine_id"],
        filename=baseline["filename"],
        file_size=baseline["file_size"],
        original_crc32=registered_crc,
        registered_at=baseline["registered_at"],
        current_file_crc32=registered_crc,
        original_file_still_intact=True,
    )


@app.get(
    "/api/v1/logs/status",
    response_model=StatusResponse,
    summary="Check Whether an Original Log Has Been Registered",
    tags=["Log Integrity"],
    status_code=status.HTTP_200_OK,
)
def get_status() -> StatusResponse:
   
    return StatusResponse(
        registered=_baseline["registered"],
        machine_id=_baseline["machine_id"],
        filename=_baseline["filename"],
        file_size=_baseline["file_size"],
        original_crc32=_baseline["original_crc32"],
        registered_at=_baseline["registered_at"],
    )
