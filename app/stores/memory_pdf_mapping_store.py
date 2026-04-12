from __future__ import annotations

from typing import Any


class MemoryPdfMappingStore:
    def __init__(self, mapping: dict[str, str], source: str = "pdf_mapping_loader") -> None:
        self._source = source
        self._mapping: dict[str, str] = dict(mapping)

    def get_pdf_filename(self, conclusion_id: str) -> str | None:
        return self._mapping.get(conclusion_id)

    def count(self) -> int:
        return len(self._mapping)

    def stats(self) -> dict[str, Any]:
        return {
            "store": self.__class__.__name__,
            "source": self._source,
            "count": len(self._mapping),
        }
