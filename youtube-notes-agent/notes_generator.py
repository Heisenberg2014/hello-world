import re
import os
from datetime import datetime
from pathlib import Path

import anthropic


def _build_system_prompt() -> str:
    return """Sei un assistente specializzato nel trasformare contenuti video in appunti strutturati e utili.
Il tuo compito è analizzare le informazioni di un video YouTube e creare appunti chiari, ben organizzati e facilmente consultabili.

Rispondi SEMPRE in italiano, indipendentemente dalla lingua del video.

Per ogni video produci:
1. Un riassunto conciso (3-5 frasi) che cattura l'essenza del contenuto
2. I punti chiave come lista numerata (massimo 10 punti)
3. Note approfondite con eventuali sezioni tematiche
4. Tag pertinenti (5-10 tag, parole singole o brevi frasi)
5. Se il trascritto è disponibile, una sezione con i momenti salienti (timestamp + descrizione)

Formato output: Markdown strutturato, pronto per essere salvato come file .md"""


def _build_user_prompt(video: dict, transcript_text: str | None) -> str:
    parts = [
        f"**Titolo:** {video['title']}",
        f"**Canale:** {video['channel']}",
        f"**URL:** {video['url']}",
        f"**Durata:** {video.get('duration', 'N/A')}",
    ]

    if video.get("published_at"):
        date = video["published_at"][:10]
        parts.append(f"**Pubblicato:** {date}")

    if video.get("description"):
        desc = video["description"][:1000]
        if len(video["description"]) > 1000:
            desc += "..."
        parts.append(f"\n**Descrizione:**\n{desc}")

    if transcript_text:
        # Limit transcript to ~8000 chars to stay within context
        if len(transcript_text) > 8000:
            transcript_text = transcript_text[:8000] + "\n...[trascritto troncato]"
        parts.append(f"\n**Trascritto:**\n{transcript_text}")
    else:
        parts.append("\n*Trascritto non disponibile — genera note basandoti su titolo, canale e descrizione.*")

    return "\n".join(parts)


def generate_notes(video: dict, transcript_text: str | None) -> str:
    """Call Claude to generate structured notes. Returns markdown content."""
    client = anthropic.Anthropic()

    full_response = []

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=_build_system_prompt(),
        messages=[
            {
                "role": "user",
                "content": _build_user_prompt(video, transcript_text),
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_response.append(text)

    print()  # newline after streaming
    return "".join(full_response)


def _slugify(text: str) -> str:
    """Convert title to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[àáâãäå]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[ìíîï]", "i", text)
    text = re.sub(r"[òóôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:80].rstrip("-")


def save_note(video: dict, notes_content: str, notes_dir: Path) -> Path:
    """Write the final Markdown file with YAML frontmatter."""
    notes_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(video["title"])
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}_{slug}.md"
    filepath = notes_dir / filename

    # Avoid filename collisions
    counter = 1
    while filepath.exists():
        filepath = notes_dir / f"{date_str}_{slug}_{counter}.md"
        counter += 1

    published = video.get("published_at", "")[:10] if video.get("published_at") else ""

    frontmatter = f"""---
title: "{video['title'].replace('"', "'")}"
channel: "{video['channel'].replace('"', "'")}"
url: "{video['url']}"
video_id: "{video['video_id']}"
duration: "{video.get('duration', '')}"
published: "{published}"
processed: "{date_str}"
has_transcript: {str(video.get('has_transcript', False)).lower()}
---

"""
    filepath.write_text(frontmatter + notes_content, encoding="utf-8")
    return filepath
