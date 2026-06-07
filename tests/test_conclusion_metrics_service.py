from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.conclusion_view_stat import ConclusionViewStat
from app.models.favorite import Favorite
from app.services.conclusion_metrics_service import ConclusionMetricsService


class ConclusionMetricsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self._session_factory = sessionmaker(bind=engine)
        self.db = self._session_factory()

    def tearDown(self) -> None:
        self.db.close()

    def test_record_view_increments_each_detail_access(self) -> None:
        self.assertEqual(ConclusionMetricsService.record_view(self.db, "I001"), 1)
        self.assertEqual(ConclusionMetricsService.record_view(self.db, "I001"), 2)

        counts = ConclusionMetricsService.get_counts_by_ids(self.db, ["I001"])
        self.assertEqual(counts["I001"]["favorite_count"], 0)
        self.assertEqual(counts["I001"]["view_count"], 2)

    def test_counts_include_existing_favorite_rows(self) -> None:
        self.db.add(Favorite(user_id="u1", conclusion_id="I001"))
        self.db.add(Favorite(user_id="u2", conclusion_id="I001"))
        self.db.add(Favorite(user_id="u3", conclusion_id="I002"))
        self.db.add(ConclusionViewStat(conclusion_id="I001", view_count=8))
        self.db.commit()

        counts = ConclusionMetricsService.get_counts_by_ids(self.db, ["I001", "I002"])

        self.assertEqual(counts["I001"]["favorite_count"], 2)
        self.assertEqual(counts["I001"]["view_count"], 8)
        self.assertEqual(counts["I002"]["favorite_count"], 1)
        self.assertEqual(counts["I002"]["view_count"], 0)


if __name__ == "__main__":
    unittest.main()
