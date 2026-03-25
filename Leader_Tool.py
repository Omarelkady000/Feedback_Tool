import streamlit as st
import re
import requests
import math
import csv
import io

# --- 1. CORE LOGIC (Preserved from your v4.5) ---
XML_TIMEBASE_MAP = {
    "10.00 fps": "10", "12.00 fps": "12", "15.00 fps": "15",
    "23.976 fps": "24", "24.00 fps": "24", "25.00 fps": "25", "29.97 fps": "30",
    "30.00 fps": "30", "50.00 fps": "50", "59.94 fps": "60", "60.00 fps": "60"
}

def tc_to_frames(tc, fps_choice):
    try:
        clean_tc = tc.replace(';', ':')
        parts = list(map(int, clean_tc.split(':')))
        h, m, s, f = parts
        total_minutes = (h * 60) + m

        if "29.97" in fps_choice:
            frame_number = ((total_minutes * 60) + s) * 30 + f
            drop_frames = 2 * (total_minutes - (total_minutes // 10))
            return frame_number - drop_frames
        elif "59.94" in fps_choice:
            frame_number = ((total_minutes * 60) + s) * 60 + f
            drop_frames = 4 * (total_minutes - (total_minutes // 10))
            return frame_number - drop_frames
        else:
            base = 24 if "23.976" in fps_choice else float(fps_choice.split(' ')[0])
            return math.floor((h * 3600 * base) + (m * 60 * base) + (s * base) + f)
    except:
        return 0

# --- 2. WEB INTERFACE SETUP ---
st.set_page_config(page_title="Premiere Workflow Tool", page_icon="🎬")
st.title("🎬 Premiere Workflow Tool")

# Creating Tabs to keep the old and new code organized
tab1, tab2 = st.tabs(["📄 Doc to XML (Editor)", "📊 CSV to Doc/XML (Leader)"])

# --- TAB 1: YOUR ORIGINAL GOOGLE DOC LOGIC ---
with tab1:
    st.header("Convert Google Doc to Markers")
    url = st.text_input("1. Google Doc URL:", placeholder="Paste link here...", key="doc_url")
    fps_choice_1 = st.selectbox("2. Select Premiere Timebase:", list(XML_TIMEBASE_MAP.keys()), index=6, key="fps1")
    custom_filename = st.text_input("3. Custom Filename (Optional):", placeholder="e.g. My_Project_Markers", key="fn1")

    if st.button("GENERATE XML", type="primary", key="btn1"):
        if not url:
            st.error("Please paste the Google Doc URL.")
        else:
            try:
                export_url = url.split('/edit')[0] + '/export?format=txt' if "/edit" in url else url
                response = requests.get(export_url)
                response.raise_for_status()
                data = response.text

                pattern = r"(\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2})(?:\s*[–-]\s*(\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2}))?([\s\S]+?)(?=\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2}|$)"
                matches = list(re.finditer(pattern, data))

                if not matches:
                    st.warning("No timecodes found. Check Doc permissions.")
                else:
                    timebase_v = XML_TIMEBASE_MAP[fps_choice_1]
                    ntsc_v = "TRUE" if (".97" in fps_choice_1 or ".94" in fps_choice_1) else "FALSE"
                    xml_header = f'<?xml version="1.0" encoding="UTF-8"?><xmeml version="4"><project><children><sequence><name>FEEDBACK_IMPORT</name><rate><timebase>{timebase_v}</timebase><ntsc>{ntsc_v}</ntsc></rate><media><video><format><samplecharacteristics><width>1920</width><height>1080</height></samplecharacteristics></format></video></media>'
                    
                    xml_markers = ""
                    for m in matches:
                        start_f = tc_to_frames(m.group(1), fps_choice_1)
                        end_f = tc_to_frames(m.group(2), fps_choice_1) if m.group(2) else start_f
                        cmt = m.group(3).strip()
                        if bool(re.search(r'\bkeep\b', cmt, re.IGNORECASE)): end_f = start_f
                        clean_cmt = cmt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        xml_markers += f"<marker><name>NOTE</name><comment>{clean_cmt}</comment><in>{int(start_f)}</in><out>{int(end_f)}</out></marker>"
                    
                    full_xml = xml_header + xml_markers + "</sequence></children></project></xmeml>"
                    
                    user_name = custom_filename.strip() if custom_filename.strip() else "Markers"
                    if not user_name.lower().endswith(".xml"): user_name += ".xml"

                    st.success(f"Found {len(matches)} markers!")
                    st.download_button(label=f"💾 Download {user_name}", data=full_xml, file_name=user_name)
            except Exception as e:
                st.error(f"Error: {e}")

# --- TAB 2: THE NEW CSV TO DOC/XML LOGIC ---
with tab2:
    st.header("Convert Premiere CSV to Doc/XML")
    st.write("Upload the CSV exported from Premiere to generate a text list for your Google Doc.")
    
    csv_file = st.file_uploader("Upload Premiere CSV", type="csv")
    fps_choice_2 = st.selectbox("Select Sequence FPS:", list(XML_TIMEBASE_MAP.keys()), index=6, key="fps2")

    if csv_file is not None:
        # Premiere CSVs are often tab-separated (\t)
        content = csv_file.getvalue().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content), delimiter='\t')
        
        doc_output = ""
        xml_markers_csv = ""
        count = 0

        for row in reader:
            # Premiere uses 'Marker Name' for the main text and 'Description' for the extra details
            # We combine them or take the longest one to ensure no feedback is lost
            m_name = row.get('Marker Name', '')
            m_desc = row.get('Description', '')
            comment = m_name if len(m_name) > len(m_desc) else m_desc
            
            in_tc = row.get('In', '00:00:00:00')
            out_tc = row.get('Out', in_tc)

            # 1. Create text for the Google Doc
            doc_output += f"{in_tc} - {out_tc}\n{comment}\n\n"

            # 2. Create XML markers
            start_f = tc_to_frames(in_tc, fps_choice_2)
            end_f = tc_to_frames(out_tc, fps_choice_2)
            clean_cmt = comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            xml_markers_csv += f"<marker><name>NOTE</name><comment>{clean_cmt}</comment><in>{int(start_f)}</in><out>{int(end_f)}</out></marker>"
            count += 1

        if count > 0:
            st.success(f"Processed {count} markers!")
            
            # XML Packaging
            timebase_2 = XML_TIMEBASE_MAP[fps_choice_2]
            ntsc_2 = "TRUE" if (".97" in fps_choice_2 or ".94" in fps_choice_2) else "FALSE"
            final_csv_xml = f'<?xml version="1.0" encoding="UTF-8"?><xmeml version="4"><project><children><sequence><name>CSV_IMPORT</name><rate><timebase>{timebase_2}</timebase><ntsc>{ntsc_2}</ntsc></rate><media><video><format><samplecharacteristics><width>1920</width><height>1080</height></samplecharacteristics></format></video></media>{xml_markers_csv}</sequence></children></project></xmeml>'

            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📝 Download Text for Doc", data=doc_output, file_name="Feedback_List.txt")
            with col2:
                st.download_button("📥 Download XML", data=final_csv_xml, file_name="CSV_to_Markers.xml")

            st.text_area("Preview for Google Doc:", doc_output, height=300)
