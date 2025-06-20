import os
import logging
import xml.etree.ElementTree as ET
import streamlit as st
from concurrent.futures import ProcessPoolExecutor, as_completed
import shutil
import concurrent.futures
import glob



def process_xml_file(file_path, output_dir):
    logging.basicConfig(filename='Log.log', level=logging.INFO, 
                       format='%(asctime)s - %(message)s')
    
    try:
        filtered_count = 0
        filtered_lines = []

        tree = ET.parse(file_path)
        root_element = tree.getroot()

        # Collect calls to remove (to avoid modifying list during iteration)
        calls_to_remove = []

        # Find and process <Call> elements
        for call in root_element.findall('.//Call'):
            xcd = call.find('XCD')
            if xcd is not None:
                # Check all required attributes and their values
                conditions = {
                    'TM': 'FEIN',
                    'SN': 'TEL',
                    'CQUM': 'Sec',
                    'SP': 'TELSP',
                    'UT': 'OUT',
                    'USN': 'TEL',
                    'ExtAmt': '0.00',
                    'UsageInd': '2'
                }
                
                # Check TZ separately as it can be either GSM or OTHER
                tz_value = xcd.get('TZ')
                tz_condition = tz_value in ['GSM', 'OTHER']
                
                # Check if all conditions are met
                all_conditions_met = all(
                    xcd.get(attr) == value 
                    for attr, value in conditions.items()
                )
                
                if all_conditions_met and tz_condition:
                    # Log the filtered call
                    filtered_lines.append(ET.tostring(call, encoding='unicode'))
                    calls_to_remove.append(call)
                    filtered_count += 1

        # Remove the calls that matched our criteria
        for call in calls_to_remove:
            # Find the parent element and remove the call
            for parent in root_element.iter():
                if call in parent:
                    parent.remove(call)
                    break

        # Create REJ file with filtered content
        if filtered_lines:
            rej_filename = f"REJ_{os.path.basename(file_path)}"
            rej_filepath = os.path.join(output_dir, rej_filename)
            
            with open(rej_filepath, 'w', encoding='utf-8') as rej_file:
                rej_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                rej_file.write('<!DOCTYPE Document SYSTEM "/export/home1/bscs9x/lisa/product/iam/prod/bscs/resource//docgenlib/BillingDocument.dtd">\n')
                rej_file.write('<Document>\n')
                for line in filtered_lines:
                    rej_file.write(line + '\n')
                rej_file.write('</Document>')

        # Save modified XML (always create output file)
        output_file_path = os.path.join(output_dir, os.path.basename(file_path))
        
        # Write the XML properly
        with open(output_file_path, 'w', encoding='utf-8') as output_file:
            output_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            output_file.write('<!DOCTYPE Document SYSTEM "/export/home1/bscs9x/lisa/product/iam/prod/bscs/resource//docgenlib/BillingDocument.dtd">\n')
            # Convert tree to string and write it
            tree_str = ET.tostring(root_element, encoding='unicode')
            output_file.write(tree_str)
        
        # Return appropriate result
        if calls_to_remove:
            return [file_path], filtered_count
        else:
            return [], filtered_count
        
    except Exception as e:
        logging.error(f"Error processing file {file_path}: {e}")
        return [], 0

def check_and_modify_xml(input_dir, output_dir):
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = []
        for xml_file in glob.glob(os.path.join(input_dir, '*.xml')):
            # Only process files that start with "DET"
            if os.path.basename(xml_file).startswith('DET'):
                future = executor.submit(process_xml_file, xml_file, output_dir)
                futures.append(future)
        
        modified_files = []
        total_filtered = 0
        
        for future in concurrent.futures.as_completed(futures):
            try:
                files, count = future.result()
                modified_files.extend(files)
                total_filtered += count
            except Exception as e:
                logging.error(f"Error in future: {e}")
                
    return modified_files, total_filtered

def main():
    st.title("XML Modifier")
    
    input_dir = st.text_input("Input Directory:")
    output_dir = st.text_input("Output Directory:")
    
    if st.button("Process XML Files"):
        if input_dir and output_dir:
            modified_files, filtered_count = check_and_modify_xml(input_dir, output_dir)
            if modified_files:
                st.success(f"Modified XML files: {len(modified_files)}. Filtered <Call> elements: {filtered_count}.")
                for file in modified_files:
                    st.write(file)
            else:
                st.warning("No files were modified.")
        else:
            st.error("Please provide both input and output directories.")

if __name__ == "__main__":
    main()