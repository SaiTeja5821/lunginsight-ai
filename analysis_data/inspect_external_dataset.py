
import gzip
from pathlib import Path

file_path = Path(
    "external_dataset/GSE40419_LC-87_RPKM_expression.txt.gz"
)

if not file_path.exists():
    print("File not found. Check the folder and filename.")
    raise SystemExit(1)

print("File size:", round(file_path.stat().st_size / (1024 * 1024), 2), "MB")

with gzip.open(file_path, "rt", encoding="utf-8", errors="replace") as f:
    for i in range(8):
        line = f.readline()
        if not line:
            break
        print(f"\nLine {i + 1}:")
        print(line[:500].rstrip())
