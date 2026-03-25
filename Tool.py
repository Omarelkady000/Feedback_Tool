import streamlit as st
import re
import requests
import math

# --- LOGIC (EXACTLY AS YOUR V4.5) ---
XML_TIMEBASE_MAP = {
    "10.00 fps": "10", "12.00 fps": "12", "15.00 fps": "15",
    "23.976 fps": "24", "24.00 fps": "24", "25.00 fps": "25", "29.97 fps": "30",
    "30.00 fps": "30", "50.00 fps": "50", "59.94 fps": "60", "60.00 fps": "60"
}

def tc_to_frames(tc, fps_choice):
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
        if "23.976" in fps_choice:
            base = 24
        else:
            base = float(fps_choice.split(' ')[0])
        return math.floor((h * 3600 * base) + (m * 60 * base) + (s * base) + f)

# --- WEB INTERFACE ---
st.set_page_config(page_title="Premiere Feedback Tool", page_icon="🎬")
st.title("🎬 Premiere Feedback Tool")
st.markdown("Convert Google Doc comments into Premiere Markers.")

# Replaces your Tkinter Entry and Combobox
url = st.text_input("Google Doc URL:", placeholder="Paste link here...")
fps_choice = st.selectbox("Select Premiere Timebase:", list(XML_TIMEBASE_MAP.keys()), index=6)

# Replaces your Tkinter Button
if st.button("GENERATE XML", type="primary"):
    if not url:
        st.error("Please paste the Google Doc URL.")
    else:
        try:
            # Logic for export URL
            export_url = url.split('/edit')[0] + '/export?format=txt' if "/edit" in url else url
            
            response = requests.get(export_url)
            response.raise_for_status()
            data = response.text

            # Exact same Pattern from your v4.5
            pattern = r"(\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2})(?:\s*[–-]\s*(\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2}))?([\s\S]+?)(?=\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2}|$)"
            matches = list(re.finditer(pattern, data))

            if not matches:
                st.warning("No timecodes found. Ensure the Doc is set to 'Anyone with the link can view'.")
            else:
                timebase_value = XML_TIMEBASE_MAP.get(fps_choice, "30")
                ntsc_value = "TRUE" if (".97" in fps_choice or ".94" in fps_choice) else "FALSE"

                xml_header = f'<?xml version="1.0" encoding="UTF-8"?><xmeml version="4"><project><children><sequence><name>FEEDBACK_IMPORT</name><rate><timebase>{timebase_value}</timebase><ntsc>{ntsc_value}</ntsc></rate><media><video><format><samplecharacteristics><width>1920</width><height>1080</height></samplecharacteristics></format></video></media>'

                xml_markers = ""
                for m in matches:
                    start_tc = m.group(1)
                    end_tc = m.group(2)
                    comment_text = m.group(3).strip()

                    start_f = tc_to_frames(start_tc, fps_choice)

                    # --- THE SURGICAL FIX FOR "KEEP" ---
                    has_keep_word = bool(re.search(r'\bkeep\b', comment_text, re.IGNORECASE))

                    if has_keep_word:
                        end_f = start_f
                    elif end_tc:
                        end_f = tc_to_frames(end_tc, fps_choice)
                    else:
                        # Default is now same as start (Single frame) as per your last logic
                        end_f = start_f

                    clean_comment = comment_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                    xml_markers += f"""
                        <marker>
                            <name>NOTE</name>
                            <comment>{clean_comment}</comment>
                            <in>{int(start_f)}</in>
                            <out>{int(end_f)}</out>
                        </marker>"""

                full_xml = xml_header + xml_markers + "</sequence></children></project></xmeml>"

                st.success(f"Found {len(matches)} markers!")
                
                # Replaces your FileDialog
                st.download_button(
                    label="💾 Download XML for Premiere",
                    data=full_xml,
                    file_name=f"Markers_{fps_choice.replace(' ', '_')}.xml",
                    mime="application/xml"
                )

        except Exception as e:
            st.error(f"Failed: {str(e)}")
