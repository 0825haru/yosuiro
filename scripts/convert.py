"""data/spots.json(元データ)から、公開用の api/ 以下のJSONを作るスクリプト。

使い方(リポジトリのルートで実行):
    python scripts/convert.py

チェックでエラーが1つでもあると、api/ は一切書き換えずに終了する。
(間違ったデータが公開されるのを防ぐため)
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "data" / "spots.json"   # 入力(元データ)
OUT_DIR = ROOT / "api"                    # 出力(公開用。手で編集しない)

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST).isoformat(timespec="seconds")

# 金沢市の座標の目安。地図で確認して、必要なら調整する
LAT_RANGE = (36.4, 36.7)
LNG_RANGE = (136.5, 136.8)

ID_PATTERN = re.compile(r"^kw-\d{3}$")
KANA_LINE = re.compile(r"^よみがな[::]")
LABEL = re.compile(r"^由来説明文[::]\s*")


def clean_description(text):
    """「よみがな:」の行と「由来説明文:」のラベルを除いた説明文を返す。空なら None"""
    if not text:
        return None
    lines = []
    for line in str(text).splitlines():
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


def to_number(value):
    """数値に変換する。できなければ None"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_rows():
    with open(SRC_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # { "spots": [...] } の形でも、[...] の形でも読めるようにする
    rows = data["spots"] if isinstance(data, dict) and "spots" in data else data
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        sys.exit("[エラー] spots.json は「[ {...}, {...} ]」の形で書いてください")
    return rows


def build(rows):
    """チェックしながら出力データを作る。(spots, details, errors, warnings, skipped) を返す"""
    spots, details = [], {}
    errors, warnings = [], []
    seen_ids = set()
    skipped = 0

    for index, row in enumerate(rows, start=1):
        spot_id = str(row.get("id") or "").strip()
        label = spot_id or f"{index}番目の要素"

        if not is_published(row.get("published")):
            skipped += 1
            continue

        # --- ID のチェック ---
        if not spot_id:
            errors.append(f"{label}: id がありません")
            continue
        if not ID_PATTERN.match(spot_id):
            errors.append(f"{label}: id は kw-001 の形式にしてください")
        if spot_id in seen_ids:
            errors.append(f"{label}: id が重複しています")
            continue
        seen_ids.add(spot_id)

        # --- 名前・用水名・説明文のチェック ---
        name = str(row.get("name") or "").strip()
        if not name:
            errors.append(f"{label}: name が空です")
        canal_name = str(row.get("canal_name") or "").strip() or None
        if canal_name is None:
            warnings.append(f"{label}: canal_name が空です")
        description = clean_description(row.get("description"))
        if description is None:
            warnings.append(f"{label}: description が空です")

        # --- 座標のチェック ---
        lat, lng = to_number(row.get("lat")), to_number(row.get("lng"))
        if lat is None or lng is None:
            errors.append(f"{label}: lat / lng が数値ではありません (lat={row.get('lat')!r}, lng={row.get('lng')!r})")
            continue
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
            errors.append(f"{label}: 座標が金沢市の範囲外です (lat={lat}, lng={lng})。緯度と経度が逆になっていないか確認してください")

        spots.append({
            "id": spot_id,
            "name": name,
            "canal_name": canal_name,
            "lat": lat,
            "lng": lng,
            "thumbnail_url": None,
        })
        details[spot_id] = {
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

    return spots, details, errors, warnings, skipped


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    rows = load_rows()
    spots, details, errors, warnings, skipped = build(rows)

    for message in warnings:
        print(f"[警告] {message}")
    for message in errors:
        print(f"[エラー] {message}")

    if errors:
        print(f"\nエラーが {len(errors)} 件あるため、api/ は更新していません。data/spots.json を直して、もう一度実行してください。")
        sys.exit(1)

    spots_dir = OUT_DIR / "spots"
    spots_dir.mkdir(parents=True, exist_ok=True)

    for spot_id, detail in details.items():
        write_json(spots_dir / f"{spot_id}.json", detail)
    write_json(OUT_DIR / "spots.json", {"spots": spots, "updated_at": NOW})

    # 公開をやめたスポット(published が false になった等)の古いファイルを消す
    removed = []
    for old in spots_dir.glob("kw-*.json"):
        if old.stem not in details:
            old.unlink()
            removed.append(old.name)

    print(f"\n{len(spots)} 件を出力しました(非公開でスキップ: {skipped} 件、警告: {len(warnings)} 件)")
    if removed:
        print(f"公開をやめたため削除したファイル: {', '.join(removed)}")


if __name__ == "__main__":
    main()