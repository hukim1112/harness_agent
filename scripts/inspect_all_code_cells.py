import json

path = "notebooks/harness/1.Reasoning.ipynb"
with open(path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for idx, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "code":
        print(f"=== Code Cell {idx} ===")
        src = "".join(cell["source"])
        print(src[:300])
        print("...")
