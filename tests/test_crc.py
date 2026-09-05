import io
import os
import sys
import tempfile

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from crc.crc_checker import (
    calculate_and_format_crc32,
    calculate_bytes_crc32,
    calculate_crc32,
    calculate_file_crc32,
    format_crc32,
)



SAMPLE_CSV_CONTENT = (
    "timestamp,machine_id,temperature,vibration,operating_status,fault_code,fault_message\n"
    "2026-09-01 10:00:00,MACHINE-001,72.5,0.21,ON,0,None\n"
    "2026-09-01 10:05:00,MACHINE-001,73.1,0.23,ON,0,None\n"
    "2026-09-01 10:10:00,MACHINE-001,74.8,0.25,ON,0,None\n"
    "2026-09-01 10:15:00,MACHINE-001,81.7,0.45,ON,101,OVERHEAT\n"
    "2026-09-01 10:20:00,MACHINE-001,79.2,0.38,ON,0,None\n"
)

SAMPLE_CSV_BYTES = SAMPLE_CSV_CONTENT.encode("utf-8")





class TestCalculateCrc32:
    
    def test_same_input_produces_same_crc(self):
        
        data = b"industrial machine log data"
        crc_first = calculate_crc32(data)
        crc_second = calculate_crc32(data)
        assert crc_first == crc_second, (
            "CRC-32 is deterministic — same bytes must always give same CRC."
        )

    def test_different_data_produces_different_crc(self):
       
        data_a = b"temperature=72.5"
        data_b = b"temperature=92.5"  
        crc_a = calculate_crc32(data_a)
        crc_b = calculate_crc32(data_b)
        assert crc_a != crc_b, (
            "Different data must produce different CRC-32 values."
        )

    def test_single_byte_change_changes_crc(self):
       
        original = bytearray(b"MACHINE-001,72.5,0.21,ON,0,None")
        modified = bytearray(original)
        modified[12] = ord("9") 

        crc_original = calculate_crc32(bytes(original))
        crc_modified = calculate_crc32(bytes(modified))

        assert crc_original != crc_modified, (
            "A single byte modification must change the CRC-32."
        )

    def test_empty_bytes_produces_valid_crc(self):
        
        result = calculate_crc32(b"")
        assert isinstance(result, int), "CRC-32 result must be an integer."
        assert 0 <= result <= 0xFFFFFFFF, (
            "CRC-32 result must fit in an unsigned 32-bit integer."
        )
        
        assert result == 0, "CRC-32 of empty bytes must be 0."

    def test_result_is_unsigned_32bit_integer(self):
       
        data = b"test data for range check"
        result = calculate_crc32(data)
        assert isinstance(result, int)
        assert result >= 0, "CRC-32 must be non-negative."
        assert result <= 0xFFFFFFFF, "CRC-32 must not exceed 32 bits."

    def test_raises_type_error_for_non_bytes(self):
        
        with pytest.raises(TypeError):
            calculate_crc32("this is a string, not bytes") 

    def test_csv_data_crc_is_deterministic(self):
        
        crc1 = calculate_crc32(SAMPLE_CSV_BYTES)
        crc2 = calculate_crc32(SAMPLE_CSV_BYTES)
        assert crc1 == crc2

    def test_byte_order_matters(self):
        
        data = b"ABCDEFGH"
        reversed_data = data[::-1]
        assert calculate_crc32(data) != calculate_crc32(reversed_data), (
            "Byte order must affect the CRC-32 value."
        )


class TestCalculateBytesCrc32:
   

    def test_valid_bytes_produce_crc(self):
       
        result = calculate_bytes_crc32(b"hello world")
        assert isinstance(result, int)
        assert result >= 0

    def test_empty_bytes_raises_value_error(self):
       
        with pytest.raises(ValueError, match="empty"):
            calculate_bytes_crc32(b"")

    def test_raises_type_error_for_string(self):
        
        with pytest.raises(TypeError):
            calculate_bytes_crc32("not bytes") 

    def test_csv_bytes_give_valid_result(self):
       
        result = calculate_bytes_crc32(SAMPLE_CSV_BYTES)
        assert 1 <= result <= 0xFFFFFFFF


class TestFormatCrc32:
   

    def test_output_is_exactly_8_characters(self):
        
        crc_value = calculate_crc32(b"test")
        formatted = format_crc32(crc_value)
        assert len(formatted) == 8, (
            f"Expected 8 characters, got {len(formatted)}: '{formatted}'"
        )

    def test_output_is_uppercase_hex(self):
        
        crc_value = 0xA82F91C4
        formatted = format_crc32(crc_value)
        assert formatted == formatted.upper(), "CRC hex output must be uppercase."
        assert all(c in "0123456789ABCDEF" for c in formatted), (
            "CRC hex output must contain only valid hex characters."
        )

    def test_zero_padded_for_small_values(self):
        
        formatted = format_crc32(1)
        assert formatted == "00000001", (
            f"Expected '00000001' for CRC value 1, got '{formatted}'"
        )

    def test_zero_crc_formats_as_eight_zeros(self):
        
        formatted = format_crc32(0)
        assert formatted == "00000000"

    def test_maximum_32bit_value(self):
        
        formatted = format_crc32(0xFFFFFFFF)
        assert formatted == "FFFFFFFF"

    def test_known_value_formats_correctly(self):
       
        formatted = format_crc32(0xDEADBEEF)
        assert formatted == "DEADBEEF"

    def test_raises_type_error_for_non_int(self):
        
        with pytest.raises(TypeError):
            format_crc32("A82F91C4")

    def test_raises_value_error_for_negative(self):
        
        with pytest.raises(ValueError):
            format_crc32(-1)

    def test_raises_value_error_for_overflow(self):
        
        with pytest.raises(ValueError):
            format_crc32(0x1_0000_0000)

    def test_no_hex_prefix(self):
        
        formatted = format_crc32(0xA82F91C4)
        assert not formatted.startswith("0x"), (
            "CRC output must not include '0x' prefix."
        )


class TestCalculateFileCrc32:
    

    def test_file_crc_matches_bytes_crc(self):
      
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(SAMPLE_CSV_BYTES)
            tmp_path = tmp.name

        try:
            file_crc = calculate_file_crc32(tmp_path)
            bytes_crc = calculate_bytes_crc32(SAMPLE_CSV_BYTES)
            assert file_crc == bytes_crc, (
                "File CRC and in-memory bytes CRC must match for the same content."
            )
        finally:
            os.unlink(tmp_path)

    def test_modifying_file_changes_crc(self):
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
            tmp.write(SAMPLE_CSV_BYTES)
            tmp_path = tmp.name

        try:
            original_crc = calculate_file_crc32(tmp_path)

            with open(tmp_path, "ab") as f:
                f.write(b"2026-09-01 11:00:00,MACHINE-001,95.0,0.80,ON,201,MOTOR_FAULT\n")

            modified_crc = calculate_file_crc32(tmp_path)

            assert original_crc != modified_crc, (
                "Appending a row to the file must change its CRC-32."
            )
        finally:
            os.unlink(tmp_path)

    def test_overwriting_single_byte_changes_crc(self):
       
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
            tmp.write(SAMPLE_CSV_BYTES)
            tmp_path = tmp.name

        try:
            original_crc = calculate_file_crc32(tmp_path)

            
            with open(tmp_path, "r+b") as f:
                data = bytearray(f.read())
               
                content_str = data.decode("utf-8")
                modified_str = content_str.replace("72.5", "92.5", 1)
                data = modified_str.encode("utf-8")
                f.seek(0)
                f.write(data)
                f.truncate()

            modified_crc = calculate_file_crc32(tmp_path)
            assert original_crc != modified_crc

        finally:
            os.unlink(tmp_path)

    def test_raises_for_nonexistent_file(self):
       
        with pytest.raises(FileNotFoundError):
            calculate_file_crc32("/nonexistent/path/to/file.csv")

    def test_raises_for_empty_file(self):
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name  
        try:
            with pytest.raises(ValueError, match="empty"):
                calculate_file_crc32(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_result_is_formatted_correctly(self):
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
            tmp.write(SAMPLE_CSV_BYTES)
            tmp_path = tmp.name

        try:
            crc_int = calculate_file_crc32(tmp_path)
            crc_hex = format_crc32(crc_int)
            assert len(crc_hex) == 8
            assert crc_hex == crc_hex.upper()
            assert all(c in "0123456789ABCDEF" for c in crc_hex)
        finally:
            os.unlink(tmp_path)

    def test_large_file_crc_is_consistent(self):
        
        lines = ["timestamp,machine_id,temperature,vibration,operating_status,fault_code,fault_message\n"]
        for i in range(2000):
            lines.append(
                f"2026-09-01 10:{i // 60:02d}:{i % 60:02d},"
                f"MACHINE-001,72.5,0.21,ON,0,None\n"
            )
        large_content = "".join(lines).encode("utf-8")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
            tmp.write(large_content)
            tmp_path = tmp.name

        try:
            file_crc = calculate_file_crc32(tmp_path)
            bytes_crc = calculate_bytes_crc32(large_content)
            assert file_crc == bytes_crc, (
                "Chunked file CRC must match in-memory bytes CRC for large files."
            )
        finally:
            os.unlink(tmp_path)


class TestCalculateAndFormatCrc32:
    

    def test_returns_8_char_uppercase_hex(self):
        
        result = calculate_and_format_crc32(b"some data")
        assert len(result) == 8
        assert result == result.upper()

    def test_consistent_with_separate_functions(self):
       
        data = SAMPLE_CSV_BYTES
        combined = calculate_and_format_crc32(data)
        separate = format_crc32(calculate_bytes_crc32(data))
        assert combined == separate

    def test_raises_for_empty_bytes(self):
        """Must raise ValueError for empty bytes input."""
        with pytest.raises(ValueError):
            calculate_and_format_crc32(b"")


# ===========================================================================
# Section 2 — CRC Integrity Demonstration Tests
# ===========================================================================


class TestCRCIntegrityDemonstration:
    """
    Demonstrates the core integrity verification workflow:
      ORIGINAL → CRC → MODIFIED → NEW CRC → MISMATCH
    These tests mirror the demonstration scenario from the README.
    """

    def test_full_workflow_original_matches_itself(self):
        """
        Registering and immediately verifying the same bytes must always
        produce a VALID (matching) result.
        """
        original_crc = format_crc32(calculate_bytes_crc32(SAMPLE_CSV_BYTES))
        current_crc = format_crc32(calculate_bytes_crc32(SAMPLE_CSV_BYTES))
        assert original_crc == current_crc

    def test_temperature_change_detected(self):
        """
        Changing a temperature value in the CSV must change the CRC,
        simulating what happens when a sensor reading is tampered with.
        """
        original_bytes = SAMPLE_CSV_BYTES
        modified_bytes = SAMPLE_CSV_BYTES.replace(b"72.5", b"92.5")

        original_crc = format_crc32(calculate_bytes_crc32(original_bytes))
        modified_crc = format_crc32(calculate_bytes_crc32(modified_bytes))

        assert original_crc != modified_crc, (
            "Changing a temperature value must change the CRC-32."
        )

    def test_deleted_row_detected(self):
        """
        Removing a row from the CSV must change the CRC,
        simulating a deleted log record.
        """
        lines = SAMPLE_CSV_BYTES.split(b"\n")
        # Remove the OVERHEAT row (index 4)
        truncated = b"\n".join(lines[:4] + lines[5:])

        original_crc = format_crc32(calculate_bytes_crc32(SAMPLE_CSV_BYTES))
        truncated_crc = format_crc32(calculate_bytes_crc32(truncated))

        assert original_crc != truncated_crc, (
            "Deleting a row must change the CRC-32."
        )

    def test_added_row_detected(self):
        """
        Adding a new row to the CSV must change the CRC,
        simulating an injected log record.
        """
        extra_row = b"2026-09-01 11:00:00,MACHINE-001,95.0,0.80,ON,201,MOTOR_FAULT\n"
        modified_bytes = SAMPLE_CSV_BYTES + extra_row

        original_crc = format_crc32(calculate_bytes_crc32(SAMPLE_CSV_BYTES))
        modified_crc = format_crc32(calculate_bytes_crc32(modified_bytes))

        assert original_crc != modified_crc, (
            "Adding a row must change the CRC-32."
        )

    def test_fault_code_change_detected(self):
        """
        Changing a fault code in the CSV must change the CRC,
        simulating alteration of fault event data.
        """
        modified_bytes = SAMPLE_CSV_BYTES.replace(b",101,OVERHEAT", b",999,UNKNOWN")

        original_crc = format_crc32(calculate_bytes_crc32(SAMPLE_CSV_BYTES))
        modified_crc = format_crc32(calculate_bytes_crc32(modified_bytes))

        assert original_crc != modified_crc, (
            "Changing a fault code must change the CRC-32."
        )

    def test_truncated_file_detected(self):
        """
        Truncating the file (keeping only first half of bytes) must change
        the CRC, simulating partial file corruption.
        """
        truncated_bytes = SAMPLE_CSV_BYTES[: len(SAMPLE_CSV_BYTES) // 2]

        original_crc = format_crc32(calculate_bytes_crc32(SAMPLE_CSV_BYTES))
        truncated_crc = format_crc32(calculate_bytes_crc32(truncated_bytes))

        assert original_crc != truncated_crc, (
            "Truncating the file must change the CRC-32."
        )

    def test_restoring_original_restores_crc(self):
        """
        After modifying bytes and then restoring them to the original,
        the CRC must return to the original value.
        """
        original_crc = format_crc32(calculate_bytes_crc32(SAMPLE_CSV_BYTES))

        # Modify
        modified_bytes = SAMPLE_CSV_BYTES.replace(b"72.5", b"92.5")
        modified_crc = format_crc32(calculate_bytes_crc32(modified_bytes))
        assert original_crc != modified_crc  # Modification detected

        # Restore
        restored_bytes = modified_bytes.replace(b"92.5", b"72.5")
        restored_crc = format_crc32(calculate_bytes_crc32(restored_bytes))
        assert original_crc == restored_crc, (
            "Restoring the original content must restore the original CRC."
        )


# ===========================================================================
# Section 3 — FastAPI API Integration Tests
# ===========================================================================


class TestAPIEndpoints:
    """
    Integration tests for the FastAPI application.
    Uses FastAPI's TestClient (backed by httpx) to make real HTTP requests
    against the application without needing a running server.
    """

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Create a TestClient for each test and reset the baseline."""
        from fastapi.testclient import TestClient
        import main as app_module

        # Reset baseline before each test so tests are independent
        app_module._baseline.update(
            {
                "registered": False,
                "machine_id": None,
                "filename": None,
                "file_size": None,
                "original_crc32": None,
                "registered_at": None,
            }
        )
        self.client = TestClient(app_module.app)

    # --- /health ---

    def test_health_check_returns_200(self):
        """GET /health must return HTTP 200."""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_body(self):
        """GET /health must return the expected JSON body."""
        response = self.client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "Industrial Machine Log Integrity Checker" in data["service"]

    # --- GET /api/v1/logs/status ---

    def test_status_unregistered(self):
        """Status endpoint must return registered=false when no log is registered."""
        response = self.client.get("/api/v1/logs/status")
        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is False
        assert data["original_crc32"] is None

    # --- POST /api/v1/crc/calculate ---

    def test_crc_calculate_valid_csv(self):
        """Calculate endpoint must return CRC for a valid CSV upload."""
        response = self.client.post(
            "/api/v1/crc/calculate",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "crc32" in data
        assert len(data["crc32"]) == 8
        assert data["crc32"] == data["crc32"].upper()
        assert data["file_size"] == len(SAMPLE_CSV_BYTES)

    def test_crc_calculate_rejects_non_csv(self):
        """Calculate endpoint must reject non-CSV files with HTTP 400."""
        response = self.client.post(
            "/api/v1/crc/calculate",
            files={"file": ("log.txt", b"some text data", "text/plain")},
        )
        assert response.status_code == 400

    def test_crc_calculate_rejects_empty_file(self):
        """Calculate endpoint must reject empty files with HTTP 400."""
        response = self.client.post(
            "/api/v1/crc/calculate",
            files={"file": ("machine_log.csv", b"", "text/csv")},
        )
        assert response.status_code == 400

    def test_crc_calculate_same_file_twice(self):
        """Two uploads of the same file must produce the same CRC."""
        r1 = self.client.post(
            "/api/v1/crc/calculate",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
        )
        r2 = self.client.post(
            "/api/v1/crc/calculate",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["crc32"] == r2.json()["crc32"]

    # --- POST /api/v1/logs/register ---

    def test_register_valid_log(self):
        """Register endpoint must return 201 and include original_crc32."""
        response = self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
            data={"machine_id": "MACHINE-001"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "original_crc32" in data
        assert len(data["original_crc32"]) == 8
        assert data["machine_id"] == "MACHINE-001"
        assert "registered successfully" in data["message"].lower()

    def test_register_rejects_missing_machine_id(self):
        """Register endpoint must reject requests without machine_id."""
        response = self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
            # No machine_id form field
        )
        assert response.status_code == 422  # FastAPI validation error

    def test_register_updates_status(self):
        """After registration, GET /status must show registered=true."""
        self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
            data={"machine_id": "MACHINE-001"},
        )
        status_response = self.client.get("/api/v1/logs/status")
        data = status_response.json()
        assert data["registered"] is True
        assert data["machine_id"] == "MACHINE-001"
        assert data["original_crc32"] is not None

    def test_register_rejects_csv_with_missing_headers(self):
        """Register must reject CSV files missing required columns."""
        bad_csv = b"timestamp,machine_id,temperature\n2026-09-01 10:00:00,MACHINE-001,72.5\n"
        response = self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", bad_csv, "text/csv")},
            data={"machine_id": "MACHINE-001"},
        )
        assert response.status_code == 400
        assert "missing" in response.json()["detail"].lower()

    
    def test_verify_before_register_returns_404(self):
        
        response = self.client.post(
            "/api/v1/logs/verify",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
        )
        assert response.status_code == 404

    def test_verify_identical_file_returns_valid(self):
       
        self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
            data={"machine_id": "MACHINE-001"},
        )
        response = self.client.post(
            "/api/v1/logs/verify",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_identical"] is True
        assert data["integrity_status"] == "VALID"
        assert data["original_crc32"] == data["current_crc32"]

    def test_verify_modified_file_returns_modified(self):
       
        self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
            data={"machine_id": "MACHINE-001"},
        )
       
        modified_bytes = SAMPLE_CSV_BYTES.replace(b"72.5", b"92.5")

        response = self.client.post(
            "/api/v1/logs/verify",
            files={"file": ("machine_log.csv", modified_bytes, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_identical"] is False
        assert data["integrity_status"] == "MODIFIED_OR_CORRUPTED"
        assert data["original_crc32"] != data["current_crc32"]

    def test_verify_response_crc_matches_calculate_crc(self):
       
        self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
            data={"machine_id": "MACHINE-001"},
        )
        verify_response = self.client.post(
            "/api/v1/logs/verify",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
        )
        calc_response = self.client.post(
            "/api/v1/crc/calculate",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
        )
        assert verify_response.json()["current_crc32"] == calc_response.json()["crc32"]

    def test_verify_added_row_detected(self):
        
        self.client.post(
            "/api/v1/logs/register",
            files={"file": ("machine_log.csv", SAMPLE_CSV_BYTES, "text/csv")},
            data={"machine_id": "MACHINE-001"},
        )
        extra_row = b"2026-09-01 11:00:00,MACHINE-001,95.0,0.80,ON,201,MOTOR_FAULT\n"
        modified_bytes = SAMPLE_CSV_BYTES + extra_row

        response = self.client.post(
            "/api/v1/logs/verify",
            files={"file": ("machine_log.csv", modified_bytes, "text/csv")},
        )
        data = response.json()
        assert data["is_identical"] is False
        assert data["integrity_status"] == "MODIFIED_OR_CORRUPTED"
