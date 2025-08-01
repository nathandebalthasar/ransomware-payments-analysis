"""
Tried to use the ID Ransomware API to fetch ransomware related addresses, but their API is
private and they do not answer requests for access (at least not to me).
"""

import hmac
import hashlib
import base64
import requests

AUTH_KEY = 'key'
AUTH_SECRET = b'secret'  # must be in bytes
IDR_API = 'https://id-ransomware.malwarehunterteam.com/api'


def idr_call(path: str):
    url = f'{IDR_API}{path}'

    uri = path.encode()

    hmac_hash = hmac.new(AUTH_SECRET, uri, hashlib.sha256).digest()

    base64_hash = base64.b64encode(hmac_hash).decode()

    headers = {
        'Authorization': f'{AUTH_KEY}:{base64_hash}'
    }

    response = requests.get(url, headers=headers, verify=False)

    if response.status_code != 200:
        raise Exception(f"{response.status_code}: {response.text}")

    return response.json()

if __name__ == '__main__':
    try:
        ransom_notes = idr_call('/ransomwares')
        for note in ransom_notes:
            print(f"{note['name']}: {note['filenames']}")
    except Exception as e:
        print(f"Error: {e}")
