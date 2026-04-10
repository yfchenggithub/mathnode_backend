from __future__ import annotations

import json
from pathlib import Path

from app.schemas.content_v2 import ConclusionRecordV2


def main() -> None:
    """
    导出 ConclusionRecordV2 的 JSON Schema。

    输出:
    - app/data/json/conclusion_record_v2.schema.json
    """
    output_path = Path("app/data/conclusion_record_v2.schema.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schema = ConclusionRecordV2.model_json_schema(
        by_alias=False, ref_template="#/$defs/{model}"
    )

    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[OK] JSON Schema exported to: {output_path}")


if __name__ == "__main__":
    main()
