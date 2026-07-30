import re
from pathlib import Path


root = Path(__file__).resolve().parent.parent
link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
failures = []

for document in root.rglob("*.md"):
    if any(part.startswith(".") for part in document.relative_to(root).parts):
        continue
    for target in link_pattern.findall(document.read_text()):
        target = target.split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        destination = (document.parent / target).resolve()
        if not destination.exists():
            failures.append(f"{document.relative_to(root)} -> {target}")

if failures:
    raise SystemExit("Broken Markdown links:\n" + "\n".join(failures))
