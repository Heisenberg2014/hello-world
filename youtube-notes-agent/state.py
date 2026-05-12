import json
from datetime import datetime
from pathlib import Path

STATE_FILE = Path("processed_videos.json")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def is_processed(video_id: str) -> bool:
    return video_id in load_state()


def mark_processed(video_id: str, note_path: str) -> None:
    state = load_state()
    state[video_id] = {
        "processed_at": datetime.now().isoformat(),
        "note_path": note_path,
    }
    save_state(state)


def get_unprocessed(video_ids: list[str]) -> list[str]:
    state = load_state()
    return [vid for vid in video_ids if vid not in state]
