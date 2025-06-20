# XML Processing and Validation Tools

This repository contains a collection of Python scripts for XML file processing, validation, and cleanup operations.

## Installation

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Scripts Overview

### 1. xml-validator_DET.py
A Streamlit web application for validating XML files with "DET" prefix.

**Features:**
- Recursive scanning of XML files in specified directory
- Memory-efficient processing using chunked reading
- Multiprocessing support for parallel validation
- NULL/empty value detection
- Large file support (up to 400MB)

**Business Rules:**
- Only processes XML files starting with "DET"
- Validates XML structure and checks for empty/NULL values
- Skips validation for specific elements: 'Document', 'CallDetails', 'Call'
- Files with NULL values are marked as invalid
- Provides detailed error reporting and processing metrics

### 2. xml-validator_NO_DET.py
Similar to xml-validator_DET.py but processes non-DET XML files.

**Business Rules:**
- Processes XML files that don't start with "DET"
- Same validation rules as xml-validator_DET.py

### 3. Xml_Call_Cleanup.py
Script for cleaning up XML call data.

**Business Rules:**
- Processes XML files containing call records
- Performs cleanup operations on call data
- Handles file transformations and data sanitization

### 4. file_comparison_app.py
Application for comparing XML files.

**Features:**
- File comparison functionality
- Difference detection between XML files
- Reporting of discrepancies

### 5. xml-validator.py
Base version of the XML validator.

**Features:**
- Core XML validation functionality
- Basic error reporting
- File structure verification

### 6. xml-validator_OK.py
Optimized version of the XML validator.

**Features:**
- Enhanced performance
- Improved memory management
- Streamlined validation process

## Common Features Across Validators

- Memory-efficient processing using mmap and iterparse
- Multiprocessing support for parallel file processing
- Detailed error reporting and validation metrics
- Progress tracking and status updates
- File size and processing time statistics

## Error Handling

All validators implement comprehensive error handling for:
- File access issues
- XML parsing errors
- Memory constraints
- System resource limitations
- Invalid file structures

## Performance Considerations

- Uses memory mapping for large file processing
- Implements garbage collection for memory management
- Configurable process count for parallel processing
- Handles files up to 400MB in size efficiently

## Requirements

See `requirements.txt` for detailed package dependencies. Key packages include:
- streamlit
- lxml
- humanize

## Usage Notes

1. Each validator script can be run independently
2. Use the Streamlit interface for interactive validation
3. Monitor system resources when processing large files
4. Adjust process count based on system capabilities
5. Check log files for detailed error information 