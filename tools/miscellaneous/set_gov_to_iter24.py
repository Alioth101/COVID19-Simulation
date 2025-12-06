import csv
from pathlib import Path

RES_PATH = Path(r"d:/Paper/localcode/COVID19_LLMbasedMultiAgentSystem/output/graph_batch/resultsP50DeepSeepV3.csv")
DEBUG_PATH = Path(r"d:/Paper/localcode/COVID19_LLMbasedMultiAgentSystem/output/graph_batch/debug.csv")

def main():
    if not RES_PATH.exists():
        print(f"Source file not found: {RES_PATH}")
        return 1

    rows = []
    with RES_PATH.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    gov_values = None
    for r in rows:
        if len(r) >= 2 and r[1].strip().lower() == "government" and r[0].strip() == "24":
            gov_values = r[2:]
            break

    if gov_values is None:
        print("政府 (Government) 在 iteration=24 的行未找到。无法继续。")
        return 2

    new_rows = []
    for r in rows:
        if len(r) >= 2 and r[1].strip().lower() == "government":
            # 保持 iteration 字段，替换后面的数值字段为 iteration 24 的值
            new_rows.append([r[0], r[1]] + gov_values)
        else:
            new_rows.append(r)

    DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEBUG_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

    print(f"已写入 {len(new_rows)} 行到 {DEBUG_PATH}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
