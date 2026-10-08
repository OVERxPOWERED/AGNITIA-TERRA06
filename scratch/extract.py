import os, re
roadmap_path = r"e:\HACKATHON\Agnitia\AGNITIA-TERRA06-files\IMPLEMENTATION_ROADMAP.md"
with open(roadmap_path, "r", encoding="utf-8") as f:
    roadmap = f.read()

# Match lines like **FILE: `config/site.yaml`** — ✅ Tested
# followed by ````yaml ... ````
blocks = re.findall(r"\*\*FILE: `(.*?)`\*\*.*?\n````\w*\n(.*?)````", roadmap, flags=re.DOTALL)

for filename, content in blocks:
    filepath = os.path.join(r"e:\HACKATHON\Agnitia\AGNITIA-TERRA06-files", filename)
    print(f"Writing {filepath}...")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
