import streamlit as st
import os
import shutil
import difflib
from concurrent.futures import ProcessPoolExecutor

def compare_files(file1, file2, output_file):
    with open(file1, 'r') as f1, open(file2, 'r') as f2:
        file1_lines = f1.readlines()
        file2_lines = f2.readlines()

    diff = difflib.unified_diff(file1_lines, file2_lines, fromfile=file1, tofile=file2)
    with open(output_file, 'w') as rej_file:
        # Write the default first line
        rej_file.write("<Call>\n")
        
        for line in diff:
            if line.startswith(' ') or line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                continue
            line_content = line[1:].strip()
            if line_content.startswith('<Call>') or line_content.startswith('<XCD') or line_content.startswith('</Call>'):
                rej_file.write(line_content + '\n')

def process_file(file_name, dir1, dir2, rej_folder):
    file1_path = os.path.join(dir1, file_name)
    file2_path = os.path.join(dir2, file_name)
    output_file_path = os.path.join(rej_folder, f"REJ_{file_name}")
    
    if os.path.isfile(file1_path) and os.path.isfile(file2_path):
        compare_files(file1_path, file2_path, output_file_path)
        return f"Compared {file_name} and differences are written to {output_file_path}"
    else:
        return f"Skipping {file_name} as it is not a valid file."

def main():
    st.title("File Comparison App")
    
    # Directory selection
    dir1 = st.text_input("Enter first directory (D1):")
    dir2 = st.text_input("Enter second directory (D2):")
    
    if st.button('Compare Files'):
        if not os.path.isdir(dir1) or not os.path.isdir(dir2):
            st.error("Please enter valid directory paths.")
            return
        
        # Create REJ folder in D2, remove if already exists
        rej_folder = os.path.join(dir2, "REJ")
        if os.path.exists(rej_folder):
            shutil.rmtree(rej_folder)
        os.makedirs(rej_folder)
        
        files1 = set(os.listdir(dir1))
        files2 = set(os.listdir(dir2))
        
        common_files = files1.intersection(files2)
        
        if not common_files:
            st.write("No common files found to compare.")
            return
        
        # Using multiprocessing to enhance performance
        with ProcessPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_file, file_name, dir1, dir2, rej_folder) for file_name in common_files]
            for future in futures:
                st.write(future.result())
    
if __name__ == "__main__":
    main()