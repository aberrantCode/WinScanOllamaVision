from pathlib import Path

root = Path("tests")
modified = []
for p in root.rglob("*.py"):
    text = p.read_text(encoding="utf-8")
    new_text = text.replace("```", "")
    if new_text != text:
        p.write_text(new_text, encoding="utf-8")
        modified.append(str(p))

print("Modified files:")
for m in modified:
    print(m)
