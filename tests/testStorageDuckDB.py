__author__ = "Hwaipy"

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta

import duckdb

from pytimetag.storage import Storage


class StorageDuckDBTest(unittest.TestCase):
    def test_storage_core_api_compatible(self):
        async def run():
            conn = duckdb.connect(":memory:")
            storage = Storage(conn, timezone="Asia/Shanghai")
            collection = "TestCollection"

            for i in range(100):
                fetch_time = (datetime.fromisoformat("2020-07-01T00:00:00+08:00") + timedelta(seconds=i)).isoformat()
                await storage.append(collection, {"Content": i}, fetch_time)

            exp = [
                {
                    "FetchTime": (datetime.fromisoformat("2020-07-01T00:00:00+08:00") + timedelta(seconds=i)).isoformat(),
                    "Data": {"Content": i},
                }
                for i in range(100)
            ]

            self.assertEqual(
                await storage.latest(collection, "FetchTime", "2020-07-01T00:01:00+08:00", {"FetchTime": 1, "_id": 0}),
                {"FetchTime": "2020-07-01T00:01:39+08:00"},
            )
            self.assertEqual(
                await storage.latest(
                    collection,
                    "FetchTime",
                    "2020-07-01T00:01:00+08:00",
                    {"FetchTime": 1, "_id": 0, "Data.Content": 1},
                ),
                exp[99],
            )
            self.assertEqual(
                await storage.first(
                    collection,
                    "FetchTime",
                    "2020-07-01T00:01:00+08:00",
                    {"FetchTime": 1, "_id": 0, "Data.Content": 1},
                ),
                exp[61],
            )
            self.assertEqual(
                await storage.range(
                    collection,
                    "2020-07-01T00:00:40+08:00",
                    "2020-07-01T00:00:48.444+08:00",
                    "FetchTime",
                    {"FetchTime": 1, "_id": 0, "Data.Content": 1},
                ),
                exp[41:49],
            )
            self.assertEqual(
                await storage.get(
                    collection,
                    "2020-07-01T00:01:20+08:00",
                    "FetchTime",
                    {"FetchTime": 1, "_id": 0, "Data.Content": 1},
                ),
                exp[80],
            )

            await storage.delete(collection, "2020-07-01T00:00:50+08:00", "FetchTime")
            self.assertIsNone(
                await storage.get(
                    collection,
                    "2020-07-01T00:00:50+08:00",
                    "FetchTime",
                    {"FetchTime": 1, "_id": 0, "Data.Content": 1},
                )
            )

            row_with_id = await storage.get(collection, "2020-07-01T00:00:00+08:00", "FetchTime", {"_id": 1})
            self.assertIsNotNone(row_with_id)
            await storage.update(collection, row_with_id["_id"], {"NewKey": "NewValue"})
            updated = await storage.get(collection, row_with_id["_id"], "_id", {"NewKey": 1})
            self.assertEqual(updated, {"NewKey": "NewValue"})

            latest_batch = await storage.latest(collection, "FetchTime", "2020-07-01T00:01:35+08:00", {"FetchTime": 1}, 10)
            self.assertEqual(
                latest_batch,
                [
                    {"FetchTime": "2020-07-01T00:01:39+08:00"},
                    {"FetchTime": "2020-07-01T00:01:38+08:00"},
                    {"FetchTime": "2020-07-01T00:01:37+08:00"},
                    {"FetchTime": "2020-07-01T00:01:36+08:00"},
                ],
            )

        asyncio.run(run())

    def test_timezone_and_dst_handling(self):
        async def run():
            conn = duckdb.connect(":memory:")
            storage = Storage(conn, timezone="America/New_York")
            collection = "TzCollection"

            # DST fallback day: 2021-11-07 in New York.
            # 05:30 UTC -> 01:30 -04:00, 06:30 UTC -> 01:30 -05:00
            await storage.append(collection, {"tag": "before_fallback"}, 1636263000.0)
            await storage.append(collection, {"tag": "after_fallback"}, 1636266600.0)

            first_row = await storage.first(collection, "FetchTime", filter={"FetchTime": 1, "Data.tag": 1})
            latest_row = await storage.latest(collection, "FetchTime", filter={"FetchTime": 1, "Data.tag": 1})

            self.assertEqual(first_row["Data"]["tag"], "before_fallback")
            self.assertTrue(first_row["FetchTime"].endswith("-04:00"))
            self.assertEqual(latest_row["Data"]["tag"], "after_fallback")
            self.assertTrue(latest_row["FetchTime"].endswith("-05:00"))

        asyncio.run(run())

    def test_storage_persistence_to_file(self):
        async def run():
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = os.path.join(tmpdir, "storage.duckdb")
                collection = "PersistCollection"

                conn1 = duckdb.connect(db_path)
                storage1 = Storage(conn1, timezone="Asia/Shanghai")
                await storage1.append(collection, {"Content": 123}, "2024-12-31T23:59:59+08:00")
                await storage1.append(collection, {"Content": 124}, "2025-01-01T00:00:01+08:00")
                conn1.close()

                conn2 = duckdb.connect(db_path)
                storage2 = Storage(conn2, timezone="Asia/Shanghai")
                first_row = await storage2.first(
                    collection,
                    "FetchTime",
                    filter={"FetchTime": 1, "Data.Content": 1},
                )
                latest_row = await storage2.latest(
                    collection,
                    "FetchTime",
                    filter={"FetchTime": 1, "Data.Content": 1},
                )

                self.assertEqual(first_row, {"FetchTime": "2024-12-31T23:59:59+08:00", "Data": {"Content": 123}})
                self.assertEqual(latest_row, {"FetchTime": "2025-01-01T00:00:01+08:00", "Data": {"Content": 124}})
                conn2.close()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
