// ============================================================
// Industrial Machine Log Integrity Checker
// Frontend JavaScript
// Backend: FastAPI running on http://127.0.0.1:8000
// ============================================================

const API_BASE = "";

// ------------------------------------------------------------
// Helper: Get HTML element by ID
// ------------------------------------------------------------

const $ = (id) => document.getElementById(id);


// ------------------------------------------------------------
// Global message display
// ------------------------------------------------------------

function showMessage(message, type = "success") {
    const box = $("globalMessage");

    box.textContent = message;
    box.className = `message ${type}`;
}

function clearMessage() {
    const box = $("globalMessage");

    box.textContent = "";
    box.className = "message hidden";
}


// ------------------------------------------------------------
// Parse FastAPI response
// ------------------------------------------------------------

async function parseResponse(response) {

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error(`Server returned HTTP ${response.status}`);
    }

    if (!response.ok) {

        const detail =
            data.detail ||
            data.message ||
            `HTTP ${response.status}`;

        throw new Error(
            typeof detail === "string"
                ? detail
                : JSON.stringify(detail)
        );
    }

    return data;
}


// ------------------------------------------------------------
// Button loading state
// ------------------------------------------------------------

function setButtonLoading(button, loading) {

    if (loading) {

        button.dataset.originalText = button.textContent;

        button.textContent = "Processing...";

        button.disabled = true;

    } else {

        button.textContent =
            button.dataset.originalText ||
            button.textContent;

        button.disabled = false;
    }
}


// ============================================================
// 1. CHECK BACKEND HEALTH
// Endpoint:
// GET /health
// ============================================================

async function checkHealth() {

    try {

        const response = await fetch(
            `${API_BASE}/health`
        );

        const data = await parseResponse(response);

        // Top-right backend indicator
        $("backendIndicator").className =
            "status-pill online";

        $("backendText").textContent =
            "Backend Online";


        // Health card
        $("healthBox").className =
            "health-box online-box";

        $("healthStatus").textContent =
            data.status === "healthy"
                ? "Backend Online"
                : "Backend Unhealthy";

    } catch (error) {

        $("backendIndicator").className =
            "status-pill offline";

        $("backendText").textContent =
            "Backend Offline";


        $("healthBox").className =
            "health-box offline-box";

        $("healthStatus").textContent =
            "Backend Unreachable";
    }
}


// ============================================================
// 2. CALCULATE CRC-32
// Endpoint:
// POST /api/v1/crc/calculate
// ============================================================

async function calculateCRC() {

    clearMessage();

    const file =
        $("calculateFile").files[0];

    // Check file selection
    if (!file) {

        showMessage(
            "Please select a CSV file first.",
            "error"
        );

        return;
    }


    const button =
        $("calculateBtn");

    setButtonLoading(button, true);


    try {

        // Create multipart form
        const form = new FormData();

        form.append("file", file);


        // Send file to FastAPI
        const response = await fetch(
            `${API_BASE}/api/v1/crc/calculate`,
            {
                method: "POST",
                body: form
            }
        );


        const data =
            await parseResponse(response);


        // Display result
        $("calculateResult")
            .classList
            .remove("hidden");


        $("calculatedCrc").textContent =
            data.crc32;


        $("calculatedMeta").textContent =
            `${data.filename} • ${data.file_size.toLocaleString()} bytes`;


        // Display CRC in hero section
        $("heroCrc").textContent =
            data.crc32;


        showMessage(
            `CRC-32 calculated successfully: ${data.crc32}`
        );

    } catch (error) {

        showMessage(
            error.message,
            "error"
        );

    } finally {

        setButtonLoading(
            button,
            false
        );
    }
}


// ============================================================
// 3. REGISTER ORIGINAL LOG
// Endpoint:
// POST /api/v1/logs/register
// ============================================================

async function registerLog() {

    clearMessage();

    const file =
        $("registerFile").files[0];

    const machineId =
        $("machineId").value.trim();


    // Check file
    if (!file) {

        showMessage(
            "Please select the original CSV file.",
            "error"
        );

        return;
    }


    // Check machine ID
    if (!machineId) {

        showMessage(
            "Please enter a machine ID, for example MACHINE-001.",
            "error"
        );

        return;
    }


    const button =
        $("registerBtn");

    setButtonLoading(
        button,
        true
    );


    try {

        const form =
            new FormData();


        form.append(
            "file",
            file
        );


        form.append(
            "machine_id",
            machineId
        );


        // Send request
        const response =
            await fetch(
                `${API_BASE}/api/v1/logs/register`,
                {
                    method: "POST",
                    body: form
                }
            );


        const data =
            await parseResponse(response);


        // Show trusted CRC
        $("heroCrc").textContent =
            data.original_crc32;


        showMessage(
            `Original log registered successfully. Trusted CRC-32: ${data.original_crc32}`
        );


        // Refresh status automatically
        await loadStatus();


        // Check stored original file
        await checkOriginal();


    } catch (error) {

        showMessage(
            error.message,
            "error"
        );

    } finally {

        setButtonLoading(
            button,
            false
        );
    }
}


// ============================================================
// 4. VERIFY LOG INTEGRITY
// Endpoint:
// POST /api/v1/logs/verify
// ============================================================

async function verifyLog() {

    clearMessage();

    const file =
        $("verifyFile").files[0];


    if (!file) {

        showMessage(
            "Please select a CSV file to verify.",
            "error"
        );

        return;
    }


    const button =
        $("verifyBtn");

    setButtonLoading(
        button,
        true
    );


    try {

        const form =
            new FormData();


        form.append(
            "file",
            file
        );


        // Send current file to backend
        const response =
            await fetch(
                `${API_BASE}/api/v1/logs/verify`,
                {
                    method: "POST",
                    body: form
                }
            );


        const data =
            await parseResponse(response);


        // Display verification result
        $("verifyResult")
            .classList
            .remove("hidden");


        $("originalCrc").textContent =
            data.original_crc32;


        $("currentCrc").textContent =
            data.current_crc32;


        $("verifyMessage").textContent =
            data.message;


        const status =
            $("verifyStatus");


        status.textContent =
            data.integrity_status;


        // -------------------------
        // File is valid
        // -------------------------

        if (data.is_identical) {

            status.className =
                "verify-status valid";


            showMessage(
                "Integrity verified: the current file matches the trusted baseline."
            );

        }

        // -------------------------
        // File is modified
        // -------------------------

        else {

            status.className =
                "verify-status modified";


            showMessage(
                "Integrity check failed: the current file differs from the trusted baseline.",
                "error"
            );
        }


    } catch (error) {

        showMessage(
            error.message,
            "error"
        );


        $("verifyResult")
            .classList
            .add("hidden");


    } finally {

        setButtonLoading(
            button,
            false
        );
    }
}


// ============================================================
// 5. GET REGISTRATION STATUS
// Endpoint:
// GET /api/v1/logs/status
// ============================================================

async function loadStatus() {

    try {

        const response =
            await fetch(
                `${API_BASE}/api/v1/logs/status`
            );


        const data =
            await parseResponse(response);


        // Registered
        $("statusRegistered").textContent =
            data.registered
                ? "YES"
                : "NO";


        // Machine ID
        $("statusMachine").textContent =
            data.machine_id ?? "—";


        // Filename
        $("statusFilename").textContent =
            data.filename ?? "—";


        // File size
        $("statusSize").textContent =
            data.file_size != null
                ? `${data.file_size.toLocaleString()} bytes`
                : "—";


        // CRC
        $("statusCrc").textContent =
            data.original_crc32 ?? "—";


        // Registration time
        $("statusTime").textContent =
            data.registered_at ?? "—";


        // Update hero CRC
        if (data.original_crc32) {

            $("heroCrc").textContent =
                data.original_crc32;
        }


    } catch (error) {

        showMessage(
            error.message,
            "error"
        );
    }
}


// ============================================================
// 6. CHECK STORED ORIGINAL FILE
// Endpoint:
// GET /api/v1/logs/original
// ============================================================

async function checkOriginal() {

    clearMessage();


    try {

        const response =
            await fetch(
                `${API_BASE}/api/v1/logs/original`
            );


        const data =
            await parseResponse(response);


        const box =
            $("originalResult");


        // -------------------------
        // Original file is intact
        // -------------------------

        if (
            data.original_file_still_intact
        ) {

            box.innerHTML = `

                <div class="original-good">

                    <strong>INTACT</strong>

                    <div>
                        Stored file matches
                        the registered CRC-32.
                    </div>

                    <small>
                        CRC-32:
                        ${data.current_file_crc32}
                    </small>

                </div>

            `;


            showMessage(
                "Original log integrity confirmed."
            );
        }


        // -------------------------
        // Original file changed
        // -------------------------

        else {

            box.innerHTML = `

                <div class="original-bad">

                    <strong>CHANGED</strong>

                    <div>
                        Stored file no longer
                        matches the registered CRC-32.
                    </div>

                    <small>
                        Current CRC-32:
                        ${data.current_file_crc32}
                    </small>

                </div>

            `;


            showMessage(
                "Warning: the stored original log has changed.",
                "error"
            );
        }


    } catch (error) {

        showMessage(
            error.message,
            "error"
        );
    }
}


// ============================================================
// 7. DISPLAY SELECTED FILE NAME
// ============================================================

function bindFileName(
    inputId,
    labelId
) {

    $(inputId)
        .addEventListener(
            "change",
            () => {

                const file =
                    $(inputId).files[0];


                $(labelId).textContent =
                    file
                        ? file.name
                        : "Choose CSV file";
            }
        );
}


// ============================================================
// BUTTON EVENT LISTENERS
// ============================================================

$("calculateBtn")
    .addEventListener(
        "click",
        calculateCRC
    );


$("registerBtn")
    .addEventListener(
        "click",
        registerLog
    );


$("verifyBtn")
    .addEventListener(
        "click",
        verifyLog
    );


$("statusBtn")
    .addEventListener(
        "click",
        loadStatus
    );


$("originalBtn")
    .addEventListener(
        "click",
        checkOriginal
    );


$("healthBtn")
    .addEventListener(
        "click",
        checkHealth
    );


// ============================================================
// FILE INPUT LISTENERS
// ============================================================

bindFileName(
    "calculateFile",
    "calculateFileName"
);


bindFileName(
    "registerFile",
    "registerFileName"
);


bindFileName(
    "verifyFile",
    "verifyFileName"
);


// ============================================================
// INITIAL PAGE LOAD
// ============================================================

// Check whether FastAPI is running
checkHealth();

// Load current registration status
loadStatus();