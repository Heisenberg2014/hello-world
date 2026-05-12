import os
import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_FILE = Path("token.json")
CREDENTIALS_FILE = Path("client_secret.json")


def get_authenticated_service():
    """Authenticate and return a YouTube API service object."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "client_secret.json not found.\n"
                    "Download it from Google Cloud Console:\n"
                    "  APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON\n"
                    "Enable the YouTube Data API v3 first."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def get_watch_later_videos(service, max_results: int = 50) -> list[dict]:
    """Fetch videos from the Watch Later playlist."""
    videos = []
    next_page_token = None

    while True:
        request = service.playlistItems().list(
            part="snippet,contentDetails",
            playlistId="WL",
            maxResults=min(max_results - len(videos), 50),
            pageToken=next_page_token,
        )
        response = request.execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            content_details = item["contentDetails"]
            video_id = content_details["videoId"]

            videos.append({
                "video_id": video_id,
                "title": snippet.get("title", "Unknown Title"),
                "channel": snippet.get("videoOwnerChannelTitle", "Unknown Channel"),
                "description": snippet.get("description", ""),
                "published_at": snippet.get("videoPublishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "playlist_item_id": item["id"],
            })

            if len(videos) >= max_results:
                return videos

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def get_video_details(service, video_ids: list[str]) -> dict[str, dict]:
    """Fetch duration and other details for a list of video IDs."""
    details = {}

    # API allows max 50 IDs per request
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = service.videos().list(
            part="contentDetails,statistics",
            id=",".join(batch),
        ).execute()

        for item in response.get("items", []):
            vid_id = item["id"]
            duration_iso = item["contentDetails"].get("duration", "PT0S")
            details[vid_id] = {
                "duration": _parse_duration(duration_iso),
                "view_count": item.get("statistics", {}).get("viewCount", "0"),
            }

    return details


def _parse_duration(iso_duration: str) -> str:
    """Convert ISO 8601 duration (PT1H2M3S) to HH:MM:SS or MM:SS."""
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return "00:00"
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def get_transcript(video_id: str, languages: list[str] = None) -> Optional[list[dict]]:
    """
    Fetch transcript for a video. Returns list of {text, start, duration} dicts,
    or None if unavailable.
    """
    try:
        langs = languages or ["it", "en", "en-US", "en-GB"]
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try manual transcripts first, then auto-generated
        try:
            transcript = transcript_list.find_manually_created_transcript(langs)
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(langs)

        return transcript.fetch()

    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception:
        return None


def format_transcript_text(transcript: list[dict]) -> str:
    """Convert transcript segments to a single readable string."""
    lines = []
    for segment in transcript:
        start = int(segment["start"])
        minutes, seconds = divmod(start, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            timestamp = f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"
        else:
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
        lines.append(f"{timestamp} {segment['text']}")
    return "\n".join(lines)
