# 🧹 XML Call Cleanup Tool

A high-performance Streamlit desktop application for batch-filtering `<Call>` records from large collections of XML billing documents. Built for telecom BSS/OSS workflows, it processes thousands of files in parallel while preserving the original folder structure and producing a full audit trail of every removed record.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Filtering Rule](#filtering-rule)
- [Output Files](#output-files)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [Using the Interface](#using-the-interface)
- [Performance Guide](#performance-guide)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Logging](#logging)
- [Troubleshooting](#troubleshooting)
- [Version History](#version-history)

---

## Overview

The XML Call Cleanup Tool reads a directory tree of XML billing documents, removes `<Call>` elements that match a specific set of criteria (zero-amount internal telephone calls), writes the cleaned files to an output directory, and saves every removed call into a separate rejection file for auditability.

It is designed to handle datasets of thousands of files efficiently, using true OS-level multiprocessing to saturate all available CPU cores simultaneously.

---

## Features

- **Batch processing** — handles thousands of XML files across nested subfolder trees in a single run
- **True parallelism** — `ProcessPoolExecutor` gives each worker its own Python interpreter, bypassing the GIL so all CPU cores run simultaneously
- **Regex pre-scan** — files with no candidate calls are detected in microseconds and skipped without any XML parsing overhead
- **Dual parser support** — automatically uses `lxml` (C-based, ~4× faster) when installed, falls back to stdlib `xml.etree.ElementTree`
- **Audit trail** — every removed `<Call>` element is saved verbatim in a `REJ_<filename>.xml` rejection file
- **Folder structure preservation** — output mirrors the exact subfolder layout of the input
- **Hard-link optimization** — unmodified files are linked instead of copied (zero bytes written, near-instant)
- **Live progress UI** — real-time progress bar, elapsed time, ETA, and files/second rate
- **Per-subfolder status badges** — visual processing/done/error indicators per folder
- **Dark-themed UI** — custom Streamlit dark theme with purple accent colors
- **Detailed logging** — all errors written to `Log.log` with timestamps and process names

---

## Filtering Rule

A `<Call>` element is removed when its child `<XCD>` element matches **all** of the following attribute conditions simultaneously:

| Attribute   | Required Value      |
|-------------|---------------------|
| `ExtAmt`    | `0.00`              |
| `UsageInd`  | `2`                 |
| `TM`        | `FEIN`              |
| `SN`        | `TEL`               |
| `TZ`        | `GSM` **or** `OTHER`|
| `CQUM`      | `Sec`               |
| `SP`        | `TELSP`             |
| `UT`        | `OUT`               |
| `USN`       | `TEL`               |

These conditions identify zero-cost outbound GSM/other telephone calls that should be excluded from billing documents.

**Example of a call that will be removed:**

```xml
<Call>
  <XCD ExtAmt="0.00" UsageInd="2" TM="FEIN" SN="TEL" TZ="GSM"
       CQUM="Sec" SP="TELSP" UT="OUT" USN="TEL" ... />
</Call>
```

---

## Output Files

For each input file, the tool produces up to two output files in the corresponding output subfolder:

### Cleaned file — `<original_filename>.xml`
The original XML file with all matching `<Call>` elements removed. The original XML declaration and DOCTYPE header are preserved exactly. If no calls were removed, the file is hard-linked (or copied) unchanged.

### Rejection file — `REJ_<original_filename>.xml`
Created only when at least one call was removed. Contains every removed `<Call>` element wrapped in a minimal XML document:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Document SYSTEM "...BillingDocument.dtd">
<Document>
  <Call>...</Call>
  <Call>...</Call>
</Document>
```

This file serves as the complete audit trail of what was filtered from each source document.

---

## Requirements

### Python
Python **3.9 or higher** is required.

### Required packages

| Package      | Purpose                              |
|--------------|--------------------------------------|
| `streamlit`  | Web UI framework                     |
| `lxml`       | Fast C-based XML parser *(optional but strongly recommended)* |

### System
- Windows 10/11, Linux, or macOS
- Minimum 4 GB RAM (32 GB recommended for very large datasets)
- Multi-core CPU recommended (the tool scales linearly with physical core count)

---

## Installation

**1. Clone or download the project**

```bash
git clone https://github.com/your-org/xml-call-cleanup.git
cd xml-call-cleanup
```

**2. Create a virtual environment (recommended)**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install streamlit lxml
```

> **Note:** `lxml` is optional but provides approximately 3–5× faster XML parsing. If it cannot be installed in your environment, the app will fall back to Python's built-in `xml.etree.ElementTree` automatically.

---

## Running the App

```bash
streamlit run Xml_Call_Cleanup_v3.py
```

Streamlit will open the app automatically in your default browser, typically at `http://localhost:8501`.

> **Windows note:** On Windows, `ProcessPoolExecutor` uses the `spawn` start method. The script is guarded with `if __name__ == "__main__"` to prevent worker processes from re-executing the Streamlit startup code. Do not remove this guard.

---

## Using the Interface

The app is divided into four numbered sections:

### Section 1 · Select Directories

Choose your **Input Parent Folder** and **Output Parent Folder** using either method:

- **📝 Type Path** — paste the full directory path directly into the text field
- **🗂️ Browse** — navigate the filesystem interactively using the folder browser buttons

The input folder must exist. The output folder must also exist (it will not be created automatically at the top level).

### Section 2 · Detected Subfolders

Once a valid input directory is selected, the app scans it and displays the number of XML files found in each subfolder. This is a preview only — no processing happens here.

### Section 3 · Parallelism Settings

Use the slider to set the number of **worker processes**. Each worker is a full OS process that runs independently on its own CPU core.

**Recommended values by hardware:**

| CPU Type | Physical Cores | Recommended Workers |
|---|---|---|
| Intel i7-1265U (this machine) | 10 | **10** |
| Intel i5 / Ryzen 5 (6-core) | 6 | 6 |
| Intel i9 / Ryzen 9 (16-core) | 16 | 14–16 |
| Server (32+ cores) | 32 | 28–32 |

Setting workers above the physical core count typically hurts performance due to context-switching overhead.

### Section 4 · Process Files

Click **🚀 Process XML Files** to start. While processing runs you will see:

- A progress bar showing overall completion
- A live status line: `files done / total | elapsed | ETA | files/s`
- Per-subfolder badges showing `⏳ processing` → `✅ done` or `❌ error`

When complete, a summary shows total files processed, files modified, calls filtered, workers used, and average speed.

---

## Performance Guide

### Understanding the bottleneck

XML parsing in Python is **CPU-bound** work. Python's Global Interpreter Lock (GIL) prevents multiple threads from executing Python bytecode simultaneously, which is why `ThreadPoolExecutor` (used in earlier versions) gave poor results even with many workers. `ProcessPoolExecutor` spawns separate OS processes, each with their own GIL, allowing true parallel execution across all CPU cores.

### Speed optimization checklist

| Action | Expected Impact |
|---|---|
| Install `lxml` (`pip install lxml`) | **3–5× faster** XML parsing |
| Set workers = physical core count | Maximum CPU saturation |
| Input and output on the same drive/filesystem | Hard-links work → zero copy overhead for clean files |
| Input and output on fast SSD | Reduces I/O wait time |
| Close other CPU-heavy applications | More cores available to workers |

### Processing pipeline per file

```
Read raw bytes (once)
       │
       ▼
Regex pre-scan (~microseconds)
       │
       ├─ No match → hard-link/copy → DONE  ← (majority of files, very fast)
       │
       └─ Match found → lxml.fromstring(raw bytes)
                              │
                              ▼
                       Iterate <Call> elements
                       Check XCD attributes
                              │
                       ┌──────┴──────┐
                    No match      Matches found
                       │              │
                  hard-link     Remove from tree
                               Write cleaned XML
                               Write REJ_*.xml
```

### Expected throughput

On an Intel i7-1265U (10 cores) with lxml installed and SSD storage, typical throughput is **15–40 files/second** depending on file size and the proportion of files containing matching calls.

---

## Architecture

### Concurrency model

```
Main Process (Streamlit UI)
│
└── ProcessPoolExecutor (max_workers processes)
        ├── Worker Process 0  ─── _process_file(file_1, out_dir)
        ├── Worker Process 1  ─── _process_file(file_2, out_dir)
        ├── Worker Process 2  ─── _process_file(file_3, out_dir)
        │   ...
        └── Worker Process N  ─── _process_file(file_N, out_dir)
```

All files across all subfolders are submitted to the pool simultaneously. Workers pull tasks from the queue as they finish — no sequential subfolder bottleneck.

### Key functions

| Function | Description |
|---|---|
| `_process_file(args)` | Core worker function. Reads file, pre-scans, parses if needed, writes output. Runs in a worker process. |
| `_xcd_matches_lxml/stdlib(xcd)` | Pure attribute filter function. Returns `True` if the XCD element meets all removal criteria. |
| `find_xml_files(input_dir)` | Walks the input directory tree and returns a dict of `{subfolder: [file_paths]}`. |
| `build_tasks(...)` | Pre-computes `(file_path, output_dir)` tuples and creates all output directories upfront. |
| `_hardlink_or_copy(src, dst)` | Attempts `os.link()` (instant, zero bytes) then falls back to `shutil.copy2()`. |
| `main()` | Streamlit UI entry point. Renders all sections and manages the processing loop. |

### Windows compatibility

The app uses `multiprocessing.get_context('spawn')` explicitly, which is the only context supported on Windows. All data passed to worker processes is plain serializable objects (strings and tuples) — no lambdas, closures, or unpicklable objects.

---

## Project Structure

```
xml-call-cleanup/
│
├── Xml_Call_Cleanup_v3.py   # Main application (current version)
├── README.md                # This file
├── Log.log                  # Runtime error log (auto-created on first run)
│
└── .streamlit/
    └── config.toml          # Dark theme config (auto-created on first run)
```

**Input / Output layout example:**

```
input/
├── SEQ0/
│   ├── billing_001.xml
│   └── billing_002.xml
└── SEQ1/
    └── billing_003.xml

output/                          ← mirrors input structure
├── SEQ0/
│   ├── billing_001.xml          ← cleaned (matching calls removed)
│   ├── REJ_billing_001.xml      ← rejection file (removed calls)
│   └── billing_002.xml          ← unchanged (hard-linked)
└── SEQ1/
    └── billing_003.xml
```

---

## Logging

All processing errors are written to `Log.log` in the working directory. The log is appended on each run and never truncated automatically.

**Log format:**
```
2025-12-11 14:32:01,423 SpawnProcess-3 - Error [billing_099.xml]: ...
```

Each entry includes a timestamp, the worker process name, and the error message. Successful file processing is not logged to keep the log file focused on actionable issues.

To clear the log between runs, delete or truncate `Log.log` manually.

---

## Troubleshooting

**App hangs immediately on Windows after clicking Process**

This is a `multiprocessing` spawn issue. Ensure the script is run as `streamlit run Xml_Call_Cleanup_v3.py` and that the `if __name__ == "__main__":` guard at the bottom of the file is intact.

**Speed is still low (< 5 files/s)**

- Confirm `lxml` is installed: run `python -c "import lxml; print(lxml.__version__)"` in your terminal. If it fails, run `pip install lxml`.
- Check that your output directory is on the same drive as the input (enables hard-linking).
- Reduce workers to match physical core count (not logical/HT count).
- Check disk I/O: if reading from a network share or slow HDD, I/O is the bottleneck and more workers won't help.

**`OSError: [WinError 87]` or similar on output write**

The output path likely contains characters that are invalid on Windows. Use a simple path without special characters.

**`REJ_` files not appearing**

This is expected — rejection files are only created for files where at least one `<Call>` was removed. If no calls matched the filter criteria in a given file, no `REJ_` file is produced for it.

**Output XML missing the DOCTYPE declaration**

Ensure you are using `Xml_Call_Cleanup_v3.py`. Earlier versions had a bug where the header was sometimes omitted for unmodified files.

**`ModuleNotFoundError: No module named 'streamlit'`**

Run `pip install streamlit` in your active Python environment.

---

## Version History

| Version | Key Changes |
|---|---|
| **v3** (current) | Switched to `ProcessPoolExecutor` for true GIL-free parallelism. Added regex pre-scan to skip clean files entirely. Single in-memory read passed directly to lxml. Hard-link optimization. Pre-created output dirs. IPC chunksize tuning. |
| **v2** | Switched from sequential to `ThreadPoolExecutor`. Added lxml optional fast path. Pre-computed output paths. Eliminated per-file `makedirs`. All subfolders submitted in parallel. |
| **v1** | Initial release. Sequential processing with basic Streamlit UI. |

---

## License

Internal tool — for authorized use within your organization only.
#   X M L _ C A L L _ C L E A N U P  
 