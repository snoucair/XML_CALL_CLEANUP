import streamlit as st
import xml.etree.ElementTree as ET
import xml.sax
import os
from pathlib import Path
import time
from lxml import etree
import concurrent.futures
import humanize

class XMLValidator(xml.sax.handler.ContentHandler):
    def __init__(self):
        self.errors = []
    
    def fatalError(self, exception):
        self.errors.append(str(exception))
    
    def error(self, exception):
        self.errors.append(str(exception))
    
    def warning(self, exception):
        self.errors.append(str(exception))

def validate_xml_iterparse(file_path):
    """
    Validates large XML files using iterative parsing to minimize memory usage
    """
    try:
        # Use lxml's iterparse for memory-efficient parsing
        context = etree.iterparse(file_path, events=('start', 'end'))
        
        # Clear the elements after we're done with them
        for event, elem in context:
            if event == 'end':
                elem.clear()
                
            # Free up memory by removing references
            while elem.getprevious() is not None:
                del elem.getparent()[0]
        
        return True, []
    except Exception as e:
        return False, [str(e)]

def validate_xml(file_path):
    """
    Validates XML files with size check and appropriate parsing method
    """
    file_size = os.path.getsize(file_path)
    
    # For files larger than 50MB, use iterative parsing
    if file_size > 50 * 1024 * 1024:  # 50MB
        return validate_xml_iterparse(file_path)
    
    # For smaller files, use regular parsing with SAX
    parser = xml.sax.make_parser()
    handler = XMLValidator()
    parser.setContentHandler(handler)
    parser.setErrorHandler(handler)
    
    try:
        parser.parse(file_path)
        if handler.errors:
            return False, handler.errors
        return True, []
    except Exception as e:
        return False, [str(e)]

def process_file(file_path):
    """
    Process a single XML file and return its validation results
    """
    file_size = os.path.getsize(file_path)
    start_time = time.time()
    is_valid, errors = validate_xml(file_path)
    end_time = time.time()
    
    return {
        'file_name': os.path.basename(file_path),
        'file_size': file_size,
        'is_valid': is_valid,
        'errors': errors,
        'processing_time': end_time - start_time
    }

def main():
    st.title("XML Folder Validator")
    
    # Folder path input
    folder_path = st.text_input("Enter the folder path containing XML files:")
    
    if folder_path and os.path.isdir(folder_path):
        # Find all XML files in the folder
        xml_files = list(Path(folder_path).rglob("*.xml"))
        
        if not xml_files:
            st.warning("No XML files found in the specified folder.")
            return
        
        st.write(f"Found {len(xml_files)} XML files.")
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Results containers
        valid_files = []
        invalid_files = []
        
        # Process files with parallel execution
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {executor.submit(process_file, str(file_path)): file_path 
                            for file_path in xml_files}
            
            for i, future in enumerate(concurrent.futures.as_completed(future_to_file)):
                result = future.result()
                
                # Update progress
                progress = (i + 1) / len(xml_files)
                progress_bar.progress(progress)
                status_text.text(f"Processing: {result['file_name']}")
                
                # Categorize results
                if result['is_valid']:
                    valid_files.append(result)
                else:
                    invalid_files.append(result)
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Display summary
        st.header("Validation Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Files", len(xml_files))
        with col2:
            st.metric("Valid Files", len(valid_files))
        with col3:
            st.metric("Invalid Files", len(invalid_files))
        
        # Display valid files
        if valid_files:
            st.subheader("✅ Valid Files")
            for result in valid_files:
                with st.expander(f"{result['file_name']} ({humanize.naturalsize(result['file_size'])})"):
                    st.write(f"Processing time: {result['processing_time']:.2f} seconds")
        
        # Display invalid files
        if invalid_files:
            st.subheader("❌ Invalid Files")
            for result in invalid_files:
                with st.expander(f"{result['file_name']} ({humanize.naturalsize(result['file_size'])})"):
                    st.write("Errors found:")
                    for error in result['errors']:
                        st.write(f"- {error}")
                    st.write(f"Processing time: {result['processing_time']:.2f} seconds")
        
    elif folder_path:
        st.error("Invalid folder path. Please enter a valid folder path.")
    
    # Add instructions
    st.sidebar.header("Instructions")
    st.sidebar.write("""
    1. Enter the full path to the folder containing XML files
    2. The app will automatically:
        - Scan for XML files recursively
        - Process each file using memory-efficient methods
        - Handle files up to 400MB in size
        - Show detailed validation results
    3. Results include:
        - File size information
        - Processing time
        - Detailed error messages for invalid files
    """)

if __name__ == "__main__":
    main()