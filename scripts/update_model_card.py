#!/usr/bin/env python3
"""Update OpenSec GDPO-4B model card on HuggingFace.

Uploads the architecture diagram and updates the model card with links.

Usage:
    python scripts/update_model_card.py --dry-run  # Show what would be done
    python scripts/update_model_card.py            # Upload to HuggingFace
"""

import argparse
from pathlib import Path

REPO_ID = "Jarrodbarnes/opensec-gdpo-4b"


def upload_image(image_path: Path, dry_run: bool = False) -> None:
    """Upload architecture diagram to model repo."""
    from huggingface_hub import upload_file

    if dry_run:
        print(f"[DRY RUN] Would upload {image_path} to {REPO_ID}/{image_path.name}")
        return

    print(f"Uploading {image_path.name}...")
    upload_file(
        path_or_fileobj=str(image_path),
        path_in_repo=image_path.name,
        repo_id=REPO_ID,
        repo_type="model",
    )
    print(f"Uploaded {image_path.name} to {REPO_ID}")


def get_current_readme(dry_run: bool = False) -> str:
    """Get current model card content."""
    from huggingface_hub import hf_hub_download

    if dry_run:
        print("[DRY RUN] Would download current README.md")
        return ""

    readme_path = hf_hub_download(
        repo_id=REPO_ID,
        filename="README.md",
        repo_type="model",
    )
    with open(readme_path) as f:
        return f.read()


def update_readme_content(content: str) -> str:
    """Update README content with image and dataset links."""
    updates_made = []

    # Add architecture image after first heading if not present
    if "opensec-design.jpeg" not in content:
        # Find the first ## heading and insert image after it
        lines = content.split("\n")
        new_lines = []
        image_inserted = False

        for i, line in enumerate(lines):
            new_lines.append(line)
            # Insert after the model description paragraph (after first blank line following # heading)
            if not image_inserted and line.startswith("# ") and "OpenSec" in line:
                # Find next paragraph break
                for j in range(i + 1, min(i + 20, len(lines))):
                    if lines[j].strip() == "" and j + 1 < len(lines) and lines[j + 1].strip() != "":
                        # Insert image reference here
                        new_lines.append("")
                        new_lines.append("![OpenSec Architecture](opensec-design.jpeg)")
                        image_inserted = True
                        updates_made.append("Added architecture diagram")
                        break
                break

        if image_inserted:
            # Reconstruct with remaining lines
            content = "\n".join(new_lines + lines[len(new_lines) - 2:])

    # Add dataset link if not present
    if "opensec-seeds" not in content:
        # Add to Model Sources section if it exists
        if "### Model Sources" in content or "## Model Sources" in content:
            dataset_line = "- **Dataset:** [opensec-seeds](https://huggingface.co/datasets/Jarrodbarnes/opensec-seeds)"
            # Find Model Sources section and add dataset link
            lines = content.split("\n")
            new_lines = []
            in_sources = False

            for line in lines:
                new_lines.append(line)
                if "Model Sources" in line:
                    in_sources = True
                elif in_sources and line.startswith("- **"):
                    # Add dataset link after other source links
                    pass
                elif in_sources and (line.startswith("##") or line.strip() == ""):
                    # End of sources section, insert before
                    if "opensec-seeds" not in "\n".join(new_lines):
                        new_lines.insert(-1, dataset_line)
                        updates_made.append("Added dataset link")
                    in_sources = False

            content = "\n".join(new_lines)

    # Ensure arXiv link is present
    if "arXiv:2601.21083" not in content and "2601.21083" not in content:
        # Add to paper link if present
        if "arXiv" not in content:
            updates_made.append("Note: arXiv link may need manual addition")

    return content, updates_made


def upload_readme(content: str, dry_run: bool = False) -> None:
    """Upload updated README to model repo."""
    from huggingface_hub import upload_file
    import tempfile

    if dry_run:
        print("[DRY RUN] Would upload updated README.md")
        print("--- Updated content preview (first 2000 chars) ---")
        print(content[:2000])
        return

    # Write to temp file and upload
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        temp_path = f.name

    print("Uploading updated README.md...")
    upload_file(
        path_or_fileobj=temp_path,
        path_in_repo="README.md",
        repo_id=REPO_ID,
        repo_type="model",
    )
    print("Updated README.md")


def main():
    parser = argparse.ArgumentParser(description="Update OpenSec model card")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    image_path = repo_root / "assets" / "opensec-design.jpeg"

    if not image_path.exists():
        print(f"Error: Image not found at {image_path}")
        return

    # Upload image
    upload_image(image_path, dry_run=args.dry_run)

    # Get and update README
    print("\nUpdating model card...")
    current_readme = get_current_readme(dry_run=args.dry_run)

    if current_readme:
        updated_readme, updates = update_readme_content(current_readme)
        if updates:
            print(f"Updates to make: {', '.join(updates)}")
            upload_readme(updated_readme, dry_run=args.dry_run)
        else:
            print("No updates needed - model card already has image and dataset links")
    elif args.dry_run:
        print("[DRY RUN] Would update README with image and dataset links")

    print(f"\nModel card: https://huggingface.co/{REPO_ID}")


if __name__ == "__main__":
    main()
