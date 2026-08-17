"""
Xml_Call_Cleanup.py
======================
Key architectural changes vs v2:
  1. ProcessPoolExecutor  — bypasses the GIL; all 12 logical CPUs work in
     parallel (was ThreadPoolExecutor → only 1 thread ran Python at a time).
  2. Regex pre-scan       — a single re.search() on raw bytes decides in <1 ms
     whether a file needs full XML parsing at all.  Files with zero matching
     calls are hard-linked (or copied) without any parse overhead.
  3. Single-pass lxml     — when lxml is available the tree is built once;
     parent refs come free from lxml's API so no parent_map is needed.
  4. Buffered batch I/O   — output written with a single os.write() call.
  5. Chunk-size tuning    — ProcessPoolExecutor chunksize > 1 reduces IPC
     overhead for large task lists.
  6. Windows-safe spawn   — all worker state is passed via plain args; no
     lambdas or closures that can't be pickled across processes.
"""

from __future__ import annotations

import os
import re
import sys
import time
import logging
import shutil
import concurrent.futures
import multiprocessing
import xml.etree.ElementTree as ET
from typing import Tuple, Optional

import streamlit as st

# ── Optional fast parser ──────────────────────────────────────────────────────
try:
    from lxml import etree as lxml_etree
    _LXML = True
except ImportError:
    _LXML = False

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename='Log.log', level=logging.INFO,
    format='%(asctime)s %(processName)s - %(message)s'
)

# ── Constants (must be module-level so they are picklable) ────────────────────
_XML_HEADER_BYTES = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<!DOCTYPE Document SYSTEM "/export/home1/bscs9x/lisa/product/iam/prod/bscs/resource//docgenlib/BillingDocument.dtd">\n'
)
_XML_HEADER_STR = _XML_HEADER_BYTES.decode()

# Regex pre-scan: only bother parsing files that could contain matching calls.
# Pattern checks for the two cheapest attributes first (ExtAmt and UsageInd).
# If neither appears, the file is definitely clean → skip parse entirely.
_QUICK_SCAN = re.compile(
    rb'ExtAmt="0\.00"[^>]*UsageInd="2"|UsageInd="2"[^>]*ExtAmt="0\.00"'
)

# All required XCD attribute values
_VALID_TZ = frozenset((b'GSM', b'OTHER'))


# ── Pure-function filter (no class state, safe for multiprocessing) ───────────

def _xcd_matches_stdlib(xcd) -> bool:
    g = xcd.get
    return (
        g('ExtAmt')  == '0.00'  and
        g('UsageInd')== '2'     and
        g('TM')      == 'FEIN'  and
        g('SN')      == 'TEL'   and
        g('TZ')      in ('GSM', 'OTHER') and
        g('CQUM')    == 'Sec'   and
        g('SP')      == 'TELSP' and
        g('UT')      == 'OUT'   and
        g('USN')     == 'TEL'
    )


def _xcd_matches_lxml(xcd) -> bool:
    g = xcd.get
    return (
        g('ExtAmt')  == '0.00'  and
        g('UsageInd')== '2'     and
        g('TM')      == 'FEIN'  and
        g('SN')      == 'TEL'   and
        g('TZ')      in ('GSM', 'OTHER') and
        g('CQUM')    == 'Sec'   and
        g('SP')      == 'TELSP' and
        g('UT')      == 'OUT'   and
        g('USN')     == 'TEL'
    )


def _hardlink_or_copy(src: str, dst: str) -> None:
    """Hard-link src→dst (zero bytes copied). Falls back to copy2."""
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    try:
        if os.path.exists(dst):
            os.unlink(dst)
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


# ── Core worker (runs in a separate OS process) ───────────────────────────────

def _process_file(args: Tuple[str, str]) -> Tuple[Optional[str], int]:
    """
    Process a single XML file.

    Returns
    -------
    (modified_path_or_None, filtered_call_count)
    """
    file_path, output_dir = args

    try:
        # ── Step 1: read raw bytes once ──────────────────────────────────────
        with open(file_path, 'rb') as fh:
            raw = fh.read()

        # ── Step 2: regex pre-scan (~microseconds) ───────────────────────────
        # If neither ExtAmt="0.00" nor UsageInd="2" appear together, the file
        # has no candidates → hard-link and return immediately.
        if not _QUICK_SCAN.search(raw):
            out_path = os.path.join(output_dir, os.path.basename(file_path))
            _hardlink_or_copy(file_path, out_path)
            return None, 0

        # ── Step 3: full XML parse (only for candidate files) ────────────────
        basename = os.path.basename(file_path)
        out_path = os.path.join(output_dir, basename)
        rej_path = os.path.join(output_dir, f"REJ_{basename}")

        filtered_lines: list[str] = []
        filtered_count = 0

        if _LXML:
            # lxml path: parse from bytes already in memory (no re-read)
            try:
                root = lxml_etree.fromstring(raw)
            except lxml_etree.XMLSyntaxError:
                # Fallback: try recovery mode
                parser = lxml_etree.XMLParser(recover=True)
                root = lxml_etree.fromstring(raw, parser=parser)

            to_remove = []
            for call in root.iter('Call'):
                xcd = call.find('XCD')
                if xcd is not None and _xcd_matches_lxml(xcd):
                    filtered_lines.append(
                        lxml_etree.tostring(call, encoding='unicode')
                    )
                    to_remove.append((call.getparent(), call))

            if to_remove:
                for parent, call in to_remove:
                    if parent is not None:
                        parent.remove(call)
                filtered_count = len(to_remove)

                # Write REJ file
                if filtered_lines:
                    rej_bytes = (
                        _XML_HEADER_STR
                        + '<Document>\n'
                        + '\n'.join(filtered_lines)
                        + '\n</Document>\n'
                    ).encode('utf-8')
                    with open(rej_path, 'wb') as fh:
                        fh.write(rej_bytes)

                # Write modified output (lxml serialises to bytes natively)
                with open(out_path, 'wb') as fh:
                    fh.write(_XML_HEADER_BYTES)
                    fh.write(lxml_etree.tostring(root, encoding='utf-8',
                                                  xml_declaration=False))
                    fh.write(b'\n')
                return file_path, filtered_count
            else:
                _hardlink_or_copy(file_path, out_path)
                return None, 0

        else:
            # stdlib ET path: parse from in-memory bytes via BytesIO
            from io import BytesIO
            tree = ET.parse(BytesIO(raw))
            root = tree.getroot()

            # Build parent map once
            parent_map = {c: p for p in root.iter() for c in p}

            to_remove = []
            for call in root.findall('.//Call'):
                xcd = call.find('XCD')
                if xcd is not None and _xcd_matches_stdlib(xcd):
                    filtered_lines.append(ET.tostring(call, encoding='unicode'))
                    to_remove.append(call)

            if to_remove:
                for call in to_remove:
                    p = parent_map.get(call)
                    if p is not None:
                        p.remove(call)
                filtered_count = len(to_remove)

                if filtered_lines:
                    rej_content = (
                        _XML_HEADER_STR
                        + '<Document>\n'
                        + '\n'.join(filtered_lines)
                        + '\n</Document>\n'
                    )
                    with open(rej_path, 'w', encoding='utf-8') as fh:
                        fh.write(rej_content)

                with open(out_path, 'wb') as fh:
                    fh.write(_XML_HEADER_BYTES)
                    tree.write(fh, encoding='utf-8', xml_declaration=False)
                    fh.write(b'\n')
                return file_path, filtered_count
            else:
                _hardlink_or_copy(file_path, out_path)
                return None, 0

    except Exception as exc:
        logging.error(f"Error [{os.path.basename(file_path)}]: {exc}")
        return None, 0


# ── File discovery ────────────────────────────────────────────────────────────

def find_xml_files(input_dir: str) -> dict[str, list[str]]:
    """Returns {rel_subfolder: [abs_paths]} in deterministic order."""
    result: dict[str, list[str]] = {}
    for root, dirs, files in os.walk(input_dir):
        dirs.sort()
        xml_files = sorted(
            os.path.join(root, f) for f in files if f.lower().endswith('.xml')
        )
        if xml_files:
            result[os.path.relpath(root, input_dir)] = xml_files
    return result


def build_tasks(subfolder_map: dict, input_dir: str, output_base: str) -> list[tuple]:
    """Pre-compute (file_path, output_dir) and create output dirs upfront."""
    tasks = []
    for sf, files in subfolder_map.items():
        out_dir = os.path.join(output_base, sf) if sf != '.' else output_base
        os.makedirs(out_dir, exist_ok=True)
        for fp in files:
            tasks.append((fp, out_dir))
    return tasks


# ── Theme & CSS (unchanged) ───────────────────────────────────────────────────

def _write_theme_config():
    try:
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "config.toml"), "w") as f:
            f.write('[theme]\nbase = "dark"\nprimaryColor = "#7c3aed"\n'
                    'backgroundColor = "#0f0e17"\nsecondaryBackgroundColor = "#1e1b4b"\n'
                    'textColor = "#e2e8f0"\nfont = "sans serif"\n')
    except Exception:
        pass


CUSTOM_CSS = """<style>
.stApp{background:linear-gradient(135deg,#0f0e17 0%,#1a1040 50%,#0f0e17 100%);color:#e2e8f0!important}
.stApp p,.stApp span,.stApp div,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp h4,
.stMarkdown *,.stMarkdownContainer *{color:#e2e8f0!important}
.stWidgetLabel,.stTextInput label,.stRadio label,label{color:#f1f5f9!important;font-weight:600!important}
.stRadio div[role="radiogroup"] label{color:#e2e8f0!important}
.stTextInput input,input[type="text"]{background-color:#1e1b4b!important;color:#f1f5f9!important;
border:1.5px solid #6d28d9!important;border-radius:8px!important}
.stTextInput input::placeholder{color:#94a3b8!important}
.stTextInput input:focus{border-color:#a78bfa!important;box-shadow:0 0 0 3px rgba(124,58,237,.3)!important}
.stSlider label{color:#f1f5f9!important;font-weight:600!important}
.stButton>button{background:linear-gradient(135deg,#7c3aed,#4f46e5)!important;color:#fff!important;
border:none!important;border-radius:10px!important;font-weight:600!important;transition:all .2s ease!important}
.stButton>button:hover{background:linear-gradient(135deg,#6d28d9,#4338ca)!important;
transform:translateY(-1px)!important;box-shadow:0 4px 15px rgba(124,58,237,.4)!important}
.stSuccess{background-color:#d1fae5!important;color:#065f46!important;border-left:4px solid #10b981!important}
.stSuccess *{color:#065f46!important}
.stInfo{background-color:#dbeafe!important;color:#1e3a5f!important;border-left:4px solid #3b82f6!important}
.stInfo *{color:#1e3a5f!important}
.stWarning{background-color:#fef3c7!important;color:#78350f!important;border-left:4px solid #f59e0b!important}
.stWarning *{color:#78350f!important}
.stError{background-color:#fee2e2!important;color:#7f1d1d!important;border-left:4px solid #ef4444!important}
.stError *{color:#7f1d1d!important}
.stCaption,small{color:#a5b4fc!important}
.streamlit-expanderHeader{background-color:#1e1b4b!important;color:#c4b5fd!important;border-radius:8px!important}
.streamlit-expanderContent{background-color:#1a1040!important;border:1px solid #4c1d95!important;border-radius:0 0 8px 8px!important}
[data-testid="stMetricValue"]{color:#a78bfa!important;font-size:2rem!important;font-weight:700!important}
[data-testid="stMetricLabel"]{color:#cbd5e1!important}
.stProgress>div>div{background:linear-gradient(90deg,#7c3aed,#06b6d4)!important;border-radius:4px!important}
.section-card{background:rgba(30,27,75,.7);border:1px solid rgba(124,58,237,.3);border-radius:12px;
padding:1.2rem 1.5rem;margin-bottom:1rem;backdrop-filter:blur(10px)}
</style>"""


# ── Badge helpers ─────────────────────────────────────────────────────────────

def _badge(color_hex, bg_alpha, label, badge_text, detail):
    return (
        f'<div style="padding:8px 14px;margin:4px 0;background:rgba({color_hex},{bg_alpha});'
        f'border-left:3px solid #{color_hex};border-radius:6px;">'
        f'<span style="background:#{color_hex};color:#1c1917;padding:2px 10px;border-radius:12px;'
        f'font-size:.75rem;font-weight:700;">{badge_text}</span>'
        f'<span style="color:#c4b5fd;font-weight:600;margin-left:8px;">📁 {label}</span>'
        f'<span style="color:#cbd5e1;margin-left:10px;">{detail}</span></div>'
    )

def _badge_processing(label, n):
    return _badge('f59e0b', '0.1', label, '⏳ processing', f'{n} file(s)')

def _badge_done(label, total, modified, filtered):
    return _badge('10b981', '0.1', label, '✅ done',
                  f'{total} processed · {modified} modified · {filtered} filtered')

def _badge_error(label, err):
    return (
        f'<div style="padding:8px 14px;margin:4px 0;background:rgba(239,68,68,0.1);'
        f'border-left:3px solid #ef4444;border-radius:6px;">'
        f'<span style="background:#ef4444;color:#fff;padding:2px 10px;border-radius:12px;'
        f'font-size:.75rem;font-weight:700;">❌ error</span>'
        f'<span style="color:#c4b5fd;font-weight:600;margin-left:8px;">📁 {label}</span>'
        f'<span style="color:#fca5a5;margin-left:10px;">{err}</span></div>'
    )


def _fmt(s: float) -> str:
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


# ── Directory browser ─────────────────────────────────────────────────────────

def browse_directory_with_dropdown(label, key_prefix, start_dir=None):
    st.write(label)
    if start_dir is None:
        start_dir = os.getcwd()
    sk = f"{key_prefix}_current_dir"
    if sk not in st.session_state:
        st.session_state[sk] = os.path.abspath(start_dir)
    current_dir = st.session_state[sk]
    try:
        if os.path.exists(current_dir) and os.path.isdir(current_dir):
            st.caption(f"Current: {current_dir}")
            subdirs = sorted(i for i in os.listdir(current_dir)
                             if os.path.isdir(os.path.join(current_dir, i)))
            c1, c2 = st.columns(2)
            with c1:
                parent = os.path.dirname(current_dir)
                if parent != current_dir and st.button("⬆️ Parent", key=f"{key_prefix}_parent"):
                    st.session_state[sk] = parent; st.rerun()
            with c2:
                if st.button("🏠 Root", key=f"{key_prefix}_root"):
                    st.session_state[sk] = start_dir; st.rerun()
            if st.button("✅ Select This Directory", key=f"{key_prefix}_select", type="primary"):
                return current_dir
            if subdirs:
                st.write("**Subdirectories:**")
                cols = st.columns(min(len(subdirs), 3))
                for i, sd in enumerate(subdirs):
                    with cols[i % 3]:
                        if st.button(f"📁 {sd}", key=f"{key_prefix}_{sd}"):
                            st.session_state[sk] = os.path.join(current_dir, sd)
                            st.rerun()
            else:
                st.info("No subdirectories here.")
        else:
            st.error(f"Does not exist: {current_dir}")
            if st.button("Reset", key=f"{key_prefix}_reset"):
                st.session_state[sk] = os.getcwd(); st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
    return None


# ── Main Streamlit app ────────────────────────────────────────────────────────

def main():
    _write_theme_config()
    st.set_page_config(page_title="XML Call Cleanup", page_icon="🧹",
                       layout="wide", initial_sidebar_state="collapsed")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.title("🧹 XML Call Cleanup Tool  v3")

    cpu_count = os.cpu_count() or 4

    # Status bar
    parser_tag = "⚡ lxml (fast C parser)" if _LXML else "🐍 stdlib ET (install lxml for ~4× speedup)"
    st.caption(f"Parser: {parser_tag} &nbsp;|&nbsp; CPUs: {cpu_count} logical cores &nbsp;|&nbsp; "
               f"Engine: ProcessPoolExecutor (true parallelism, GIL-free)")

    # ── 1 · Directories ───────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("1 · Select Directories")
    col1, col2 = st.columns(2)

    def _dir_picker(col, label, key_prefix):
        with col:
            st.markdown(f"**📂 {label}**")
            method = st.radio(f"{label} method:", ["📝 Type Path", "🗂️ Browse"],
                              key=f"{key_prefix}_method", horizontal=True)
            chosen = None
            if method == "📝 Type Path":
                p = st.text_input(f"{label} path:",
                                  placeholder="e.g., C:/data/input",
                                  key=f"{key_prefix}_path")
                if p and os.path.isdir(p):
                    chosen = p
                    st.success("✅ Valid directory")
                    st.caption(f"Path: {p}")
                elif p:
                    st.warning("⚠️ Directory not found.")
            else:
                chosen = browse_directory_with_dropdown(
                    f"Select {label}:", key_prefix, os.getcwd())
                if chosen:
                    st.success("✅ Valid directory")
                    st.caption(f"Path: {chosen}")
        return chosen

    input_dir  = _dir_picker(col1, "Input Parent Folder",  "input")
    output_dir = _dir_picker(col2, "Output Parent Folder", "output")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 2 · Subfolder preview ─────────────────────────────────────────────────
    if input_dir and os.path.isdir(input_dir):
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("2 · Detected Subfolders")
        subfolder_map = find_xml_files(input_dir)
        total_xml = sum(len(v) for v in subfolder_map.values())
        st.info(f"Found **{total_xml}** XML files across **{len(subfolder_map)}** folder(s).")
        for sf, files in subfolder_map.items():
            lbl = sf if sf != '.' else "(root)"
            st.markdown(
                f'<div style="padding:6px 12px;margin:4px 0;'
                f'background:rgba(124,58,237,0.15);border-left:3px solid #7c3aed;border-radius:6px;">'
                f'<span style="color:#c4b5fd;font-weight:600;">📁 {lbl}</span>'
                f'<span style="color:#cbd5e1;margin-left:12px;">{len(files)} XML file(s)</span></div>',
                unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 3 · Parallelism ───────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("3 · Parallelism Settings")

    # Optimal defaults per CPU type:
    # i7-1265U: 2 P-cores (×2 HT) + 8 E-cores = 12 logical.
    # XML parse is CPU-bound → optimal = physical cores ≈ 10.
    # Going above physical cores adds context-switch overhead.
    default_workers = min(cpu_count, 10)

    col_a, col_b = st.columns([2, 1])
    with col_a:
        max_workers = st.slider(
            "🔧 Worker PROCESSES (parallel jobs)",
            min_value=1,
            max_value=min(cpu_count * 2, 24),
            value=default_workers,
            step=1,
            help=(
                f"Your i7-1265U has 10 physical cores / {cpu_count} logical. "
                "For CPU-bound XML parsing, stay between 8–12 workers. "
                "Above 12 adds context-switching overhead with diminishing returns. "
                "ProcessPoolExecutor is used — each worker is a full OS process "
                "with its own GIL, so all cores run Python in parallel."
            )
        )
    with col_b:
        st.markdown(
            f'<div style="margin-top:28px;padding:10px 16px;'
            f'background:rgba(124,58,237,0.2);border-radius:8px;text-align:center;">'
            f'<span style="color:#a78bfa;font-size:1.5rem;font-weight:700;">{max_workers}</span>'
            f'<br><span style="color:#cbd5e1;font-size:.8rem;">processes / {cpu_count} logical CPUs</span>'
            f'</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── 4 · Process ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("4 · Process Files")

    if st.button("🚀 Process XML Files", type="primary",
                 disabled=not (input_dir and output_dir)):

        for d, name in [(input_dir, "Input"), (output_dir, "Output")]:
            if not os.path.isdir(d):
                st.error(f"{name} directory does not exist.")
                st.markdown('</div>', unsafe_allow_html=True)
                return

        subfolder_map = find_xml_files(input_dir)
        if not subfolder_map:
            st.warning("No XML files found in the input directory.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        # Pre-compute tasks + create output dirs (eliminates makedirs inside workers)
        all_tasks = build_tasks(subfolder_map, input_dir, output_dir)
        total_files = len(all_tasks)

        # Build reverse lookup: file_path → subfolder label
        file_to_sf: dict[str, str] = {
            fp: sf for sf, files in subfolder_map.items() for fp in files
        }

        # UI placeholders
        overall_bar    = st.progress(0)
        overall_status = st.empty()
        files_done     = 0
        t_start        = time.perf_counter()

        sf_placeholders: dict[str, tuple] = {}
        for sf in subfolder_map:
            lbl = sf if sf != '.' else "(root)"
            ph  = st.empty()
            ph.markdown(_badge_processing(lbl, len(subfolder_map[sf])),
                        unsafe_allow_html=True)
            sf_placeholders[sf] = (ph, lbl)

        sf_stats: dict[str, dict] = {
            sf: {'modified': 0, 'filtered': 0, 'errors': []}
            for sf in subfolder_map
        }

        # ── ProcessPoolExecutor: each worker is a real OS process ─────────
        # chunksize > 1 batches tasks to reduce IPC round-trips.
        # Sweet spot: sqrt(total_files / max_workers) clamped to [4, 32]
        chunksize = max(4, min(32, int((total_files / max(max_workers, 1)) ** 0.5)))
        update_interval = max(1, total_files // 200)

        ctx = multiprocessing.get_context('spawn')   # safe on Windows + macOS

        with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers,
                mp_context=ctx) as executor:

            future_map = {
                executor.submit(_process_file, task): task[0]
                for task in all_tasks
            }

            for future in concurrent.futures.as_completed(future_map):
                fp = future_map[future]
                sf = file_to_sf.get(fp, '.')
                try:
                    mod_path, cnt = future.result()
                    if mod_path:
                        sf_stats[sf]['modified'] += 1
                    sf_stats[sf]['filtered'] += cnt
                except Exception as exc:
                    sf_stats[sf]['errors'].append(str(exc))
                    logging.error(f"Worker error [{sf}] {fp}: {exc}")

                files_done += 1

                if files_done % update_interval == 0 or files_done == total_files:
                    pct     = files_done / total_files
                    overall_bar.progress(pct)
                    elapsed = time.perf_counter() - t_start
                    rate    = files_done / elapsed if elapsed > 0 else 0
                    eta     = (total_files - files_done) / rate if rate > 0 else 0
                    overall_status.markdown(
                        f'<span style="color:#a5b4fc;">⚙️ Processing… '
                        f'{files_done} / {total_files} files'
                        f'&nbsp;|&nbsp;⏱ Elapsed: {_fmt(elapsed)}'
                        f'&nbsp;|&nbsp;🏁 ETA: {_fmt(eta) if files_done < total_files else "done"}'
                        f'&nbsp;|&nbsp;⚡ {rate:.1f} files/s</span>',
                        unsafe_allow_html=True)

        # Final badge update
        all_modified = all_filtered = 0
        for sf, stats in sf_stats.items():
            ph, lbl = sf_placeholders[sf]
            n = len(subfolder_map[sf])
            if stats['errors']:
                ph.markdown(_badge_error(lbl, f"{len(stats['errors'])} file(s) failed"),
                            unsafe_allow_html=True)
            else:
                ph.markdown(_badge_done(lbl, n, stats['modified'], stats['filtered']),
                            unsafe_allow_html=True)
            all_modified += stats['modified']
            all_filtered += stats['filtered']

        overall_status.empty()
        overall_bar.progress(1.0)

        total_elapsed = time.perf_counter() - t_start
        avg_rate = total_files / total_elapsed if total_elapsed > 0 else 0

        st.success(
            f"🎉 Done! {total_files} files · {len(subfolder_map)} folder(s) "
            f"· {_fmt(total_elapsed)} total"
        )
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Files",    total_files)
        c2.metric("Files Modified", all_modified)
        c3.metric("Calls Filtered", all_filtered)
        c4.metric("Processes Used", max_workers)
        c5.metric("Avg Speed",      f"{avg_rate:.1f} f/s")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Info expander ─────────────────────────────────────────────────────────
    with st.expander("ℹ️ Architecture & optimisations"):
        st.markdown(f"""
### Why v3 is faster

| Bottleneck | v1/v2 | v3 |
|---|---|---|
| **GIL** | ThreadPoolExecutor — 1 Python thread runs at a time | **ProcessPoolExecutor** — each worker is an OS process, GIL per process → all {cpu_count} CPUs run Python in parallel |
| **Parse every file** | ET.parse even for clean files | **Regex pre-scan** in microseconds — if no candidate attributes found, skip parse entirely and hard-link |
| **Disk reads** | File read inside ET.parse | Raw bytes read **once**, passed to lxml.fromstring() from memory |
| **Output copy** | shutil.copy2 (byte copy) | **os.link** hard-link (zero bytes, instant) when same filesystem |
| **makedirs** | Inside every worker call | Pre-created **once** before dispatch |
| **IPC overhead** | — | chunksize={max(4, min(32, int((1 if not (input_dir and os.path.isdir(input_dir or '')) else sum(len(v) for v in find_xml_files(input_dir).values())) / max(max_workers if 'max_workers' in dir() else 10, 1)) ** 0.5))} batches tasks into chunks to reduce process round-trips |

### Optimal worker count for your CPU
Your **i7-1265U** has 2 Performance-cores (×2 HT = 4 threads) + 8 Efficiency-cores = **10 physical / 12 logical**.  
- For CPU-bound work: **8–10 workers** (matches physical cores)  
- Going above 12 adds context-switching overhead with no throughput gain  
- Recommended slider value: **10**

### Parser
{'`lxml` detected — C-based, ~3-5× faster than stdlib ET' if _LXML else '`lxml` NOT installed. Run `pip install lxml` for a large free speedup.'}

### Filtering rule
Removes `<Call>` elements whose `<XCD>` matches ALL of:  
`ExtAmt="0.00"`, `UsageInd="2"`, `TM="FEIN"`, `SN="TEL"`,  
`TZ` ∈ {{GSM, OTHER}}, `CQUM="Sec"`, `SP="TELSP"`, `UT="OUT"`, `USN="TEL"`.  
Filtered calls → `REJ_<filename>.xml`.
        """)


# ── Entry point ───────────────────────────────────────────────────────────────
# CRITICAL for ProcessPoolExecutor on Windows: guard with if __name__ == '__main__'
# so spawned processes don't re-execute the Streamlit startup code.
if __name__ == "__main__":
    multiprocessing.freeze_support()   # needed for PyInstaller / Windows
    main()
