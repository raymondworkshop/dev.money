import argparse
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def has_front_matter(content: str) -> bool:
    return content.startswith("---\n")


def add_front_matter(content: str, fields: dict[str, str]) -> str:
    if has_front_matter(content):
        return content
    front_matter = "\n".join(f'{key}: "{value}"' for key, value in fields.items())
    return f"---\n{front_matter}\n---\n\n{content}"


def normalize_quartz_links(content: str) -> str:
    """Point Obsidian-style folder index links at Quartz folder pages."""
    content = re.sub(r"\[\[([^|\]]+)/_index\|", r"[[\1|", content)
    content = re.sub(r"\[\[([^|\]]+)/_index\]\]", r"[[\1]]", content)
    return content


def resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def prepare_content(wiki_dir: Path, content_dir: Path) -> None:
    if not wiki_dir.exists():
        raise FileNotFoundError(f"Wiki directory not found: {wiki_dir}")

    if content_dir.exists():
        shutil.rmtree(content_dir)
    content_dir.mkdir(parents=True, exist_ok=True)

    for source in wiki_dir.rglob("*"):
        if not source.is_file():
            continue
        rel = source.relative_to(wiki_dir)
        if rel.parts and rel.parts[0].startswith("."):
            continue
        if source.name == "INDEX.md":
            target = content_dir / "index.md"
        elif source.name == "_index.md":
            target = content_dir / rel.parent / "index.md"
        else:
            target = content_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() == ".md":
            content = source.read_text(encoding="utf-8")
            content = normalize_quartz_links(content)
            if source.name == "INDEX.md":
                content = add_front_matter(
                    content,
                    {
                        "title": "News Wiki",
                        "created": "2026-05-30",
                    },
                )
            target.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy curated business wiki content into the Quartz content folder."
    )
    parser.add_argument("--wiki", default="newswiki/wiki", help="Source wiki directory")
    parser.add_argument(
        "--content", default="site/content", help="Destination Quartz content directory"
    )
    args = parser.parse_args()

    wiki_dir = resolve_path(args.wiki)
    content_dir = resolve_path(args.content)
    prepare_content(wiki_dir, content_dir)
    print(f"Prepared Quartz content: {wiki_dir} -> {content_dir}")


if __name__ == "__main__":
    main()
