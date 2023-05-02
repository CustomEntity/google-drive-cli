#!/usr/bin/env python

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

from googleapiclient.http import MediaIoBaseDownload
from rich.console import Console
from rich.table import Table
from rich.progress import track, Progress
from rich.prompt import Prompt

SCOPES = ['https://www.googleapis.com/auth/drive']

creds = None

if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    with open('token.json', 'w') as token:
        token.write(creds.to_json())


class GoogleDriveElement:
    def __init__(self, file_id, name, mime_type):
        self.file_id = file_id
        self.name = name
        self.mime_type = mime_type

    def __repr__(self):
        return f"GoogleDriveFile({self.file_id}, {self.name}, {self.mime_type})"

    def is_folder(self):
        return self.mime_type == "application/vnd.google-apps.folder"


class GoogleDriveService:
    def __init__(self, creds):
        self.service = build('drive', 'v3', credentials=creds)

    def _recurse_folders(self, folder_id, path=""):
        result = []

        results = self.service.files().list(
            q=f"parents='{folder_id}'", fields="nextPageToken, files(id, name, mimeType)").execute()
        items = results.get("files", [])
        for item in items:
            google_drive_element = GoogleDriveElement(
                item["id"], path + item["name"], item["mimeType"])
            if item["mimeType"] == "application/vnd.google-apps.folder":
                result.append(google_drive_element)
                self._recurse_folders(item["id"], path + item["name"] + "/")
            else:
                result.append(google_drive_element)

        return result

    def list_files(self, query):
        results = []

        list_result = self.service.files().list(
            q=query, fields="nextPageToken, files(id, name, mimeType)").execute()
        items = list_result.get("files", [])
        for item in items:
            google_drive_element = GoogleDriveElement(
                item["id"], item["name"], item["mimeType"])
            if item["mimeType"] == "application/vnd.google-apps.folder":
                results.append(google_drive_element)
                results.extend(self._recurse_folders(google_drive_element.file_id, google_drive_element.name + "/"))
            else:
                results.append(google_drive_element)
        return results


google_drive_service = GoogleDriveService(creds)

console = Console()

table = Table(title="Google Drive Files")
table.add_column("ID", style="cyan")
table.add_column("Name")
table.add_column("Type")

files = google_drive_service.list_files("'root' in parents")
for file in files:
    if file.is_folder():
        table.add_row(file.file_id, "📁 " + file.name, file.mime_type)
    else:
        table.add_row(file.file_id, "📄 " + file.name, file.mime_type)

console.print(table)

file_id = Prompt.ask("Enter the ID of the file to download")
save_path = Prompt.ask("Enter the path to save the file:", default=os.getcwd())

file = google_drive_service.service.files().get(fileId=file_id).execute()
file_path = os.path.join(save_path, file["name"])

with Progress() as progress:
    task = progress.add_task("[cyan]Downloading", total=100)
    with open(file_path, "wb") as f:
        request = google_drive_service.service.files().get_media(fileId=file_id)
        media = MediaIoBaseDownload(f, request, chunksize=1024 * 1024)
        done = False
        while not done:
            status, done = media.next_chunk()
            progress.update(task, completed=int(status.progress() * 100))
