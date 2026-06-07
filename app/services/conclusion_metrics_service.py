"""Runtime metrics for conclusion cards and detail pages."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.request_context import get_request_id
from app.models.conclusion_view_stat import ConclusionViewStat
from app.models.favorite import Favorite

LOGGER = logging.getLogger(__name__)


def _normalize_ids(ids: list[str]) -> list[str]:
    normalized_ids: list[str] = []
    seen_ids: set[str] = set()
    for raw_id in ids:
        conclusion_id = str(raw_id or "").strip()
        if not conclusion_id or conclusion_id in seen_ids:
            continue

        normalized_ids.append(conclusion_id)
        seen_ids.add(conclusion_id)

    return normalized_ids


def _empty_counts(conclusion_ids: list[str]) -> dict[str, dict[str, int]]:
    return {
        conclusion_id: {
            "favorite_count": 0,
            "view_count": 0,
        }
        for conclusion_id in conclusion_ids
    }


class ConclusionMetricsService:
    @staticmethod
    def record_view(db: Session | None, conclusion_id: str) -> int:
        conclusion_id = str(conclusion_id or "").strip()
        if db is None or not conclusion_id:
            return 0

        try:
            stat = db.execute(
                select(ConclusionViewStat).where(
                    ConclusionViewStat.conclusion_id == conclusion_id
                )
            ).scalar_one_or_none()

            if stat is None:
                stat = ConclusionViewStat(
                    conclusion_id=conclusion_id,
                    view_count=1,
                )
                db.add(stat)
            else:
                stat.view_count = max(0, int(stat.view_count or 0)) + 1
                stat.updated_at = datetime.utcnow()

            db.commit()
            return max(0, int(stat.view_count or 0))
        except IntegrityError:
            db.rollback()
            return ConclusionMetricsService._increment_existing_view_count(
                db=db,
                conclusion_id=conclusion_id,
            )
        except SQLAlchemyError as exc:
            db.rollback()
            LOGGER.warning(
                "conclusion view record failed | request_id=%s conclusion_id=%s reason=%s",
                get_request_id(),
                conclusion_id,
                exc,
            )
            return 0

    @staticmethod
    def _increment_existing_view_count(db: Session, conclusion_id: str) -> int:
        try:
            stat = db.execute(
                select(ConclusionViewStat).where(
                    ConclusionViewStat.conclusion_id == conclusion_id
                )
            ).scalar_one_or_none()
            if stat is None:
                return 0

            stat.view_count = max(0, int(stat.view_count or 0)) + 1
            stat.updated_at = datetime.utcnow()
            db.commit()
            return max(0, int(stat.view_count or 0))
        except SQLAlchemyError as exc:
            db.rollback()
            LOGGER.warning(
                "conclusion view retry failed | request_id=%s conclusion_id=%s reason=%s",
                get_request_id(),
                conclusion_id,
                exc,
            )
            return 0

    @staticmethod
    def get_counts_by_ids(
        db: Session | None,
        ids: list[str],
    ) -> dict[str, dict[str, int]]:
        conclusion_ids = _normalize_ids(ids)
        counts_by_id = _empty_counts(conclusion_ids)
        if db is None or not conclusion_ids:
            return counts_by_id

        try:
            favorite_rows = db.execute(
                select(Favorite.conclusion_id, func.count(Favorite.id))
                .where(Favorite.conclusion_id.in_(conclusion_ids))
                .group_by(Favorite.conclusion_id)
            ).all()
            for conclusion_id, count in favorite_rows:
                key = str(conclusion_id or "").strip()
                if key in counts_by_id:
                    counts_by_id[key]["favorite_count"] = max(0, int(count or 0))

            view_rows = db.execute(
                select(
                    ConclusionViewStat.conclusion_id,
                    ConclusionViewStat.view_count,
                ).where(ConclusionViewStat.conclusion_id.in_(conclusion_ids))
            ).all()
            for conclusion_id, count in view_rows:
                key = str(conclusion_id or "").strip()
                if key in counts_by_id:
                    counts_by_id[key]["view_count"] = max(0, int(count or 0))
        except SQLAlchemyError as exc:
            LOGGER.warning(
                "conclusion metrics query failed | request_id=%s id_count=%s reason=%s",
                get_request_id(),
                len(conclusion_ids),
                exc,
            )

        return counts_by_id

    @staticmethod
    def append_counts_to_items(db: Session | None, items: Any) -> None:
        if not isinstance(items, list):
            return

        ids = [
            str(item.get("id") or "").strip()
            for item in items
            if isinstance(item, dict)
        ]
        counts_by_id = ConclusionMetricsService.get_counts_by_ids(db=db, ids=ids)

        for item in items:
            if not isinstance(item, dict):
                continue

            conclusion_id = str(item.get("id") or "").strip()
            counts = counts_by_id.get(
                conclusion_id,
                {"favorite_count": 0, "view_count": 0},
            )
            item["favorite_count"] = counts["favorite_count"]
            item["view_count"] = counts["view_count"]

    @staticmethod
    def append_counts_to_payload(db: Session | None, payload: dict[str, Any]) -> None:
        conclusion_id = str(payload.get("id") or "").strip()
        counts = ConclusionMetricsService.get_counts_by_ids(
            db=db,
            ids=[conclusion_id],
        ).get(
            conclusion_id,
            {"favorite_count": 0, "view_count": 0},
        )
        payload["favorite_count"] = counts["favorite_count"]
        payload["view_count"] = counts["view_count"]