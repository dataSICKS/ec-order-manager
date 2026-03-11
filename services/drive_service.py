import os
import json                                                                                                               
from datetime import datetime                                                                                           
from google.oauth2 import service_account                                                                                 
from googleapiclient.discovery import build                                                                             
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io


def get_drive_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def upload_csv(csv_content: bytes, filename: str = None) -> str:
    service = get_drive_service()
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

    if not filename:
        today = datetime.now().strftime("%Y%m%d")
        filename = f"出荷依頼_{today}.csv"

    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(csv_content), mimetype="text/csv")

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    return file.get("webViewLink", "")


def list_files(folder_id: str = None) -> list:
    service = get_drive_service()
    folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, createdTime, webViewLink)",
        orderBy="createdTime desc",
        pageSize=20
    ).execute()

    return results.get("files", [])


def download_file(file_id: str) -> bytes:
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()