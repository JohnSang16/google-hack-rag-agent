"""
One-time OAuth setup for Google Drive doc creation.

Steps:
  1. Go to console.cloud.google.com → project gen-lang-client-0169091300
  2. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
  3. Choose "Desktop app", download JSON, save as drive_client_secrets.json here
  4. Run: python3 setup_drive_oauth.py
  5. Approve in browser — done. Token saved to drive_oauth_token.json
"""
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]
SECRETS_FILE = "drive_client_secrets.json"
TOKEN_FILE = "drive_oauth_token.json"


def main():
    if not os.path.exists(SECRETS_FILE):
        print(f"ERROR: {SECRETS_FILE} not found.")
        print("Download it from GCP Console → APIs & Services → Credentials → OAuth 2.0 Client ID")
        return

    flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"Token saved to {TOKEN_FILE}")
    print("Doc creation will now run as your Google account.")


if __name__ == "__main__":
    main()
