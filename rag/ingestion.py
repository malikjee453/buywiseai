from pathlib import Path

def save_markdown_document(folder, filename, body, metadata=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    metadata = metadata or {}
    header = "---\n" + "\n".join(f"{k}: {v}" for k, v in metadata.items()) + "\n---\n"
    (folder / filename).write_text(header + "\n" + body, encoding="utf-8")
