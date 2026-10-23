import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# このファイルの場所から、リポジトリのルートを求める
ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "data" / "spots.json"   # 入力(元データ)
OUT_DIR = ROOT / "api"                    # 出力(公開用)

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST).isoformat(timespec="seconds")

# 「よみがな:」「由来説明文:」(半角・全角コロン両対応)
KANA_LINE = re.compile(r"^よみがな[::]")
LABEL = re.compile(r"^由来説明文[::]\s*")


def clean_description(text):
    """ラベルを取り除いた説明文を返す。空なら None"""
    if not text:
        return None
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if KANA_LINE.match(line):
            continue
        line = LABEL.sub("", line)
        if line:
            lines.append(line)
    return "".join(lines) or None


def is_published(value):
    """true / 1 / "1" を公開扱いにする"""
    return value is True or value == 1 or value == "1"


def main():
    with open(SRC_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    (OUT_DIR / "spots").mkdir(parents=True, exist_ok=True)
    spots = []
    seen_ids = set()

    for row in rows:
        if not is_published(row.get("published")):
            continue

        spot_id = row["id"]
        if spot_id in seen_ids:
            raise ValueError(f"IDが重複しています: {spot_id}")
        seen_ids.add(spot_id)

        name = row["name"]
        canal_name = row.get("canal_name") or None
        lat = float(row["lat"])   # 文字列で書かれていても数値にする
        lng = float(row["lng"])
        description = clean_description(row.get("description"))

        if description is None:
            print(f"[警告] {spot_id}: description が空です")

        spots.append({
            "id": spot_id,
            "name": name,
            "canal_name": canal_name,
            "lat": lat,
            "lng": lng,
            "thumbnail_url": None,
        })

        detail = {
            "id": spot_id,
            "lang": "ja",
            "is_fallback": False,
            "name": name,
            "canal_name": canal_name,
            "description": description,
            "lat": lat,
            "lng": lng,
            "media": [],
            "updated_at": NOW,
        }
        (OUT_DIR / "spots" / f"{spot_id}.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT_DIR / "spots.json").write_text(
        json.dumps({"spots": spots, "updated_at": NOW}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"{len(spots)} 件を出力しました")


if __name__ == "__main__":
    main()