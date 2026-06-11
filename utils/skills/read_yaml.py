import glob

import yaml


def parse_frontmatter() -> None:
    print("Scanning for SKILL.md files...")
    skill_files = glob.glob("**/SKILL.md", recursive=True)

    for file_path in skill_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    print(f"\nFile: {file_path}")
                    print(f"Name: {frontmatter.get('name', 'N/A')}")
                    print(f"Description: {frontmatter.get('description', 'N/A')}")
        except Exception as e:
            print(f"Error reading {file_path}: {e}")


def main() -> None:
    parse_frontmatter()


if __name__ == "__main__":
    main()
