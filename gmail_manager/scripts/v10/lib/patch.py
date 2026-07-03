from pathlib import Path

def replace_once(file_path, search_text, replacement_text):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(str(path))

    content = path.read_text(encoding="utf-8")

    if search_text not in content:
        raise ValueError(f"Texte introuvable dans {path}")

    if replacement_text in content:
        return False

    content = content.replace(search_text, replacement_text, 1)
    path.write_text(content, encoding="utf-8")
    return True


def append_if_missing(file_path, marker, content_to_append):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(str(path))

    content = path.read_text(encoding="utf-8")

    if marker in content:
        return False

    content = content.rstrip() + "\n\n" + content_to_append.strip() + "\n"
    path.write_text(content, encoding="utf-8")
    return True
