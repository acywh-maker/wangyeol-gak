"""노션 모든 시즌의 유튜브 영상 길이를 wangyeol/youtube_lengths.json에 저장한다 (로컬에서 실행 후 커밋).

    python scripts/build_youtube_lengths.py

배포 서버(Streamlit Cloud)에서는 유튜브가 watch 페이지를 막아 영상 길이를 못 읽는다.
그러면 영상이 0분으로 잡혀 시즌이 1~2화로 줄어들기 때문에, 길이를 파일로 함께 올린다.
노션에 새 영상을 넣으면 다시 실행해서 커밋한다. 이미 있는 항목은 그대로 두고 새 영상만 더한다.
"""
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

from wangyeol import notion  # noqa: E402


def main() -> None:
    saved = notion._saved_lengths()
    missing = []
    for row in notion.list_seasons():
        ids = notion._youtube_ids(notion._season_blocks(row["id"]))
        for vid in sorted(ids - saved.keys()):
            info = notion.youtube_from_watch(vid)
            if info:
                saved[vid] = info
            else:
                missing.append((row["title"], vid))
        print(f"{row['title']}: 영상 {len(ids)}개")
    notion.YOUTUBE_LENGTHS.write_text(json.dumps(saved, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"저장: {len(saved)}개 → {notion.YOUTUBE_LENGTHS.name}")
    for title, vid in missing:
        print(f"길이를 못 읽음: {title} / {vid}")


if __name__ == "__main__":
    main()
