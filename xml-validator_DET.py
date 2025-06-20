import streamlit as st
import os
from pathlib import Path
import time
from lxml import etree
import multiprocessing
import humanize
import gc
import mmap
import traceback

# Set page config must be the first Streamlit command
st.set_page_config(layout="wide", page_title="XML Validator")

def check_file_accessibility(file_path):
    try:
        with open(file_path, 'rb') as f:
            f.read(1024)
        return True, ""
    except Exception as e:
        return False, str(e)

def validate_xml_in_chunks(file_path):
    try:
        null_errors = []
        parser = etree.XMLParser(huge_tree=True, recover=True)
        skip_elements = {'Document', 'CallDetails', 'Call'}
        
        with open(file_path, 'rb') as xml_file:
            with mmap.mmap(xml_file.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                context = etree.iterparse(mm, events=('start', 'end'))
                
                try:
                    for event, elem in context:
                        if event == 'start':
                            if elem.tag not in skip_elements:
                                for attr_name, attr_value in elem.attrib.items():
                                    if attr_value.strip() == "":
                                        null_errors.append(f"Empty value in attribute '{attr_name}' of element '{elem.tag}'")
                                
                                if elem.text is not None and elem.text.strip() == "":
                                    null_errors.append(f"Empty value in element '{elem.tag}'")
                        
                        if event == 'end':
                            elem.clear()
                            while elem.getprevious() is not None:
                                del elem.getparent()[0]
                
                except Exception as e:
                    return False, [f"Error during parsing: {str(e)}"]
                
                finally:
                    del context
                    gc.collect()
        
        return (False, null_errors) if null_errors else (True, [])
    
    except Exception as e:
        return False, [f"File processing error: {str(e)}"]

def process_file(file_path):
    try:
        file_size = os.path.getsize(file_path)
        start_time = time.time()
        
        access_check = check_file_accessibility(file_path)
        if not access_check[0]:
            return {
                'file_name': os.path.basename(file_path),
                'full_path': file_path,
                'file_size': file_size,
                'is_valid': False,
                'errors': [f"File access error: {access_check[1]}"],
                'processing_time': 0
            }
        
        is_valid, errors = validate_xml_in_chunks(file_path)
        end_time = time.time()
        
        return {
            'file_name': os.path.basename(file_path),
            'full_path': file_path,
            'file_size': file_size,
            'is_valid': is_valid,
            'errors': errors,
            'processing_time': end_time - start_time
        }
    
    except Exception as e:
        return {
            'file_name': os.path.basename(file_path),
            'full_path': file_path,
            'file_size': 0,
            'is_valid': False,
            'errors': [f"Processing error: {str(e)}"],
            'processing_time': 0
        }

def process_files_concurrently(xml_files, num_processes):
    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(process_file, xml_files)
    return results

def main():
    try:
        st.title("XML Folder Validator")
        
        folder_path = st.text_input("Enter the folder path containing XML files:")
        
        num_processes = st.number_input("Number of processes (default: CPU core count)", 
                                        min_value=1, 
                                        max_value=multiprocessing.cpu_count()*2, 
                                        value=multiprocessing.cpu_count())
        
        if st.button("Start Validation"):
            if folder_path and os.path.isdir(folder_path):
                xml_files = [file for file in Path(folder_path).rglob("*.xml") if file.name.startswith("DET")]
                
                if not xml_files:
                    st.warning("No XML files starting with 'DET' found in the specified folder.")
                    return
                
                st.write(f"Found {len(xml_files)} XML files starting with 'DET'.")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                results = process_files_concurrently(xml_files, num_processes)
                
                progress_bar.progress(1.0)
                status_text.text("Processing complete!")
                
                valid_files = [result for result in results if result['is_valid']]
                invalid_files = [result for result in results if not result['is_valid']]
                
                st.header("Validation Summary")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Files", len(xml_files))
                with col2:
                    st.metric("Invalid Files", len(invalid_files), delta=len(invalid_files), delta_color="inverse")
                with col3:
                    st.metric("Valid Files", len(valid_files), delta=len(valid_files), delta_color="normal")
                
                if invalid_files:
                    st.subheader("❌ Invalid Files")
                    for result in invalid_files:
                        with st.expander(f"{result['file_name']} ({humanize.naturalsize(result['file_size'])})"):
                            st.write("Full path:", result['full_path'])
                            st.write("Errors found:")
                            for error in result['errors']:
                                st.error(f"• {error}")
                            if result['processing_time'] > 0:
                                st.write(f"Processing time: {result['processing_time']:.2f} seconds")
                
                if valid_files:
                    st.subheader("✅ Valid Files")
                    for result in valid_files:
                        with st.expander(f"{result['file_name']} ({humanize.naturalsize(result['file_size'])})"):
                            st.write("Full path:", result['full_path'])
                            st.success("All validations passed")
                            st.write(f"Processing time: {result['processing_time']:.2f} seconds")
            
            elif folder_path:
                st.error("Invalid folder path. Please enter a valid folder path.")
        
        st.sidebar.header("Instructions")
        st.sidebar.write("""
        1. Enter the full path to the folder containing XML files
        2. Choose the number of processes to use (default is your CPU core count)
        3. Click "Start Validation"
        4. The app will:
            - Scan for XML files recursively
            - Process each file using memory-efficient methods
            - Check for NULL/empty values (except for 'Document', 'CallDetails', and 'Call' elements)
            - Handle large files (up to 400MB)
        5. Validation rules:
            - XML structure must be well-formed
            - No empty/NULL values allowed (except for specified elements)
            - Files with NULL values will be marked as invalid
        6. Results show:
            - Invalid files first
            - Detailed error messages
            - File sizes and processing times
        7. Multiprocessing:
            - The script uses multiprocessing to utilize multiple CPU cores
            - You can adjust the number of processes based on your system's capabilities
        """)
    
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        st.error(traceback.format_exc())

if __name__ == "__main__":
    main()