import re
import requests
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import math

# Updated Map: Clean mappings for Premiere XML
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


def run_tool():
    url = url_entry.get().strip()
    fps_choice = fps_combo.get()
    timebase_value = XML_TIMEBASE_MAP.get(fps_choice, "30")
    ntsc_value = "TRUE" if (".97" in fps_choice or ".94" in fps_choice) else "FALSE"

    if not url:
        messagebox.showerror("Error", "Paste the Google Doc URL.")
        return

    export_url = url.split('/edit')[0] + '/export?format=txt' if "/edit" in url else url

    try:
        response = requests.get(export_url)
        response.raise_for_status()
        data = response.text

        # Pattern captures: Timecode1, optional Timecode2, and the full Comment
        pattern = r"(\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2})(?:\s*[–-]\s*(\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2}))?([\s\S]+?)(?=\d{2}[:;]\d{2}[:;]\d{2}[:;]\d{2}|$)"
        matches = list(re.finditer(pattern, data))

        xml_header = f'<?xml version="1.0" encoding="UTF-8"?><xmeml version="4"><project><children><sequence><name>FEEDBACK_IMPORT</name><rate><timebase>{timebase_value}</timebase><ntsc>{ntsc_value}</ntsc></rate><media><video><format><samplecharacteristics><width>1920</width><height>1080</height></samplecharacteristics></format></video></media>'

        xml_markers = ""
        for m in matches:
            start_tc = m.group(1)
            end_tc = m.group(2)
            comment_text = m.group(3).strip()

            start_f = tc_to_frames(start_tc, fps_choice)

            # --- THE SURGICAL FIX FOR "KEEP" ---
            # Using Regex \b (word boundary) ensures we find 'keep' even in long paragraphs
            # while ignoring words like 'keeper' or 'keeping'.
            has_keep_word = bool(re.search(r'\bkeep\b', comment_text, re.IGNORECASE))

            if has_keep_word:
                # If 'keep' is mentioned anywhere, In and Out are identical
                end_f = start_f
            elif end_tc:
                # If an explicit range was provided (00:01 - 00:05), use it
                end_f = tc_to_frames(end_tc, fps_choice)
            else:
                # Default duration of 10 frames
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

        save_path = filedialog.asksaveasfilename(defaultextension=".xml",
                                                 initialfile=f"Markers_{fps_choice.replace(' ', '_')}.xml")
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(full_xml)
            messagebox.showinfo("Success", "XML Generated!")

    except Exception as e:
        messagebox.showerror("Error", f"Failed: {str(e)}")


# --- GUI ---
root = tk.Tk()
root.title("Premiere Feedback Tool v4.5")
root.geometry("500x250")

tk.Label(root, text="Google Doc URL:", font=("Arial", 10, "bold")).pack(pady=10)
url_entry = tk.Entry(root, width=60)
url_entry.pack()

tk.Label(root, text="Select Premiere Timebase:", font=("Arial", 10, "bold")).pack(pady=10)
fps_options = list(XML_TIMEBASE_MAP.keys())
fps_combo = ttk.Combobox(root, values=fps_options, state="readonly", width=25)
fps_combo.set("29.97 fps")
fps_combo.pack()

btn = tk.Button(root, text="GENERATE XML", command=run_tool, bg="#21a366", fg="white", font=("Arial", 11, "bold"),
                width=25)
btn.pack(pady=20)

root.mainloop()