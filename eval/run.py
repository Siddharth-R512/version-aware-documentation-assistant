# The Harness File
import json
from pathlib import Path

def load_golden(path: str) -> list[dict]:
    """Read golden.jsonl. Assert 50 items - fail loud if the frozen file item count is not 50"""
    golden = []
    path_w = Path(path)

    with path_w.open("r", encoding='utf-8') as f:
        for line in f:
            if line.strip():
                golden.append(json.loads(line))

    assert len(golden) == 50, f"Expected 50 golden items. Found {len(golden)}. Frozen file modified?"
    return golden

if __name__ == "__main__":
    golden = load_golden('eval/golden.jsonl')
    print(golden[:5])