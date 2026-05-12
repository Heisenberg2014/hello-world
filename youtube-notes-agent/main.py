#!/usr/bin/env python3
"""
YouTube Watch Later → Appunti Markdown

Uso:
  python main.py                  # processa tutti i video non ancora processati
  python main.py --limit 5        # processa al massimo 5 video
  python main.py --reprocess ID   # riprocessa un video specifico per ID
  python main.py --list           # mostra i video nella Watch Later
  python main.py --status         # mostra quanti video sono già stati processati
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from youtube_client import (
    get_authenticated_service,
    get_watch_later_videos,
    get_video_details,
    get_transcript,
    format_transcript_text,
)
from notes_generator import generate_notes, save_note
from state import is_processed, mark_processed, get_unprocessed, load_state


def get_notes_dir() -> Path:
    return Path(os.getenv("NOTES_DIR", "./notes"))


def cmd_list(args):
    """Mostra i video nella Watch Later."""
    print("Connessione a YouTube...")
    service = get_authenticated_service()
    videos = get_watch_later_videos(service, max_results=args.limit or 50)

    state = load_state()
    print(f"\n{'#':<4} {'✓':<3} {'Titolo':<60} {'Canale':<30} {'ID'}")
    print("-" * 120)
    for i, video in enumerate(videos, 1):
        done = "✓" if video["video_id"] in state else " "
        title = video["title"][:58]
        channel = video["channel"][:28]
        print(f"{i:<4} {done:<3} {title:<60} {channel:<30} {video['video_id']}")

    print(f"\nTotale: {len(videos)} video | Processati: {sum(1 for v in videos if v['video_id'] in state)}")


def cmd_status(args):
    """Mostra statistiche sullo stato di elaborazione."""
    state = load_state()
    print(f"Video processati totali: {len(state)}")
    if state:
        print("\nUltimi 10 processati:")
        items = sorted(state.items(), key=lambda x: x[1]["processed_at"], reverse=True)[:10]
        for vid_id, info in items:
            print(f"  {vid_id}  →  {info['note_path']}  ({info['processed_at'][:10]})")


def _process_video(video: dict, notes_dir: Path) -> bool:
    """Processa un singolo video. Restituisce True se ha avuto successo."""
    print(f"\n{'='*70}")
    print(f"📹 {video['title']}")
    print(f"   Canale: {video['channel']}")
    print(f"   URL: {video['url']}")

    # Fetch transcript
    print("   Recupero trascritto...", end=" ", flush=True)
    transcript = get_transcript(video["video_id"])
    if transcript:
        transcript_text = format_transcript_text(transcript)
        video["has_transcript"] = True
        print(f"✓ ({len(transcript)} segmenti)")
    else:
        transcript_text = None
        video["has_transcript"] = False
        print("✗ non disponibile")

    # Generate notes with Claude
    print("\n   Generazione appunti con Claude...\n")
    try:
        notes_content = generate_notes(video, transcript_text)
    except Exception as e:
        print(f"\n   ✗ Errore durante la generazione: {e}")
        return False

    # Save Markdown file
    note_path = save_note(video, notes_content, notes_dir)
    mark_processed(video["video_id"], str(note_path))
    print(f"\n   ✓ Salvato: {note_path}")
    return True


def cmd_process(args):
    """Processa i video non ancora processati."""
    notes_dir = get_notes_dir()

    print("Connessione a YouTube...")
    service = get_authenticated_service()

    max_fetch = (args.limit or 50) * 3  # fetch more to find unprocessed ones
    print(f"Recupero Watch Later (max {max_fetch})...")
    videos = get_watch_later_videos(service, max_results=max_fetch)

    # Filter to unprocessed only
    unprocessed_ids = get_unprocessed([v["video_id"] for v in videos])
    unprocessed = [v for v in videos if v["video_id"] in unprocessed_ids]

    if not unprocessed:
        print("\n✓ Tutti i video nella Watch Later sono già stati processati.")
        return

    # Apply --limit
    if args.limit:
        unprocessed = unprocessed[: args.limit]

    # Enrich with duration info
    print(f"Recupero dettagli per {len(unprocessed)} video...")
    details = get_video_details(service, [v["video_id"] for v in unprocessed])
    for video in unprocessed:
        vid_details = details.get(video["video_id"], {})
        video["duration"] = vid_details.get("duration", "")

    print(f"\nDa processare: {len(unprocessed)} video → cartella: {notes_dir}")

    success = 0
    failed = 0
    for video in unprocessed:
        ok = _process_video(video, notes_dir)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"✓ Completato: {success} processati, {failed} errori")
    print(f"  Appunti salvati in: {notes_dir.resolve()}")


def cmd_reprocess(args):
    """Riprocessa un video specifico (sovrascrive la nota esistente)."""
    notes_dir = get_notes_dir()

    print("Connessione a YouTube...")
    service = get_authenticated_service()

    # Fetch video info directly
    response = service.videos().list(
        part="snippet,contentDetails",
        id=args.reprocess,
    ).execute()

    items = response.get("items", [])
    if not items:
        print(f"✗ Video non trovato: {args.reprocess}")
        sys.exit(1)

    item = items[0]
    snippet = item["snippet"]
    from youtube_client import _parse_duration
    video = {
        "video_id": args.reprocess,
        "title": snippet.get("title", "Unknown"),
        "channel": snippet.get("channelTitle", "Unknown"),
        "description": snippet.get("description", ""),
        "published_at": snippet.get("publishedAt", ""),
        "url": f"https://www.youtube.com/watch?v={args.reprocess}",
        "duration": _parse_duration(item["contentDetails"].get("duration", "PT0S")),
    }

    _process_video(video, notes_dir)


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Watch Later → Appunti Markdown con Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # Default command (no subcommand = process)
    parser.add_argument("--limit", type=int, help="Numero massimo di video da processare")
    parser.add_argument("--list", action="store_true", help="Mostra video nella Watch Later")
    parser.add_argument("--status", action="store_true", help="Mostra stato elaborazione")
    parser.add_argument("--reprocess", metavar="VIDEO_ID", help="Riprocessa un video specifico")

    args = parser.parse_args()

    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("✗ ANTHROPIC_API_KEY non impostata. Crea un file .env o imposta la variabile d'ambiente.")
        sys.exit(1)

    if args.list:
        cmd_list(args)
    elif args.status:
        cmd_status(args)
    elif args.reprocess:
        cmd_reprocess(args)
    else:
        cmd_process(args)


if __name__ == "__main__":
    main()
