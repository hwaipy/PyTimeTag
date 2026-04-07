__license__ = "GNU General Public License v3"
__author__ = "Hwaipy"
__email__ = "hwaipy@gmail.com"

import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import duckdb


class Storage:
    Data = "Data"
    RecordTime = "RecordTime"
    FetchTime = "FetchTime"
    Key = "Key"

    def __init__(self, db: duckdb.DuckDBPyConnection, timezone: str = "utc"):
        self.db = db
        self.tz = self._load_timezone(timezone)
        self.existCollections = None

    async def append(self, collection: str, data: Dict[str, Any], fetchTime: Optional[Any] = None):
        await self.__beforeModify(collection)
        record_dt = datetime.now(tz=self.tz)
        fetch_dt = self.__parseFetchTime(fetchTime) if fetchTime is not None else record_dt
        self.db.execute(
            f"""
            INSERT INTO "{self.__table_name(collection)}"
            (_id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                self.__to_epoch_us(record_dt),
                self.__to_epoch_us(fetch_dt),
                json.dumps(data, ensure_ascii=True),
                json.dumps({}, ensure_ascii=True),
            ],
        )

    async def latest(
        self,
        collection: str,
        by: str = FetchTime,
        after: Optional[str] = None,
        filter: Dict[str, Any] = {},
        length: int = 1,
    ):
        rows = self.__query_rows(collection, by=by, desc=True, limit=length, after=after)
        docs = [self.__apply_projection(self.__reformResult(row), filter) for row in rows if self.__after_ok(after, row)]
        if len(docs) == 0:
            return None
        if len(docs) == 1:
            return docs[0]
        return docs

    async def first(
        self,
        collection: str,
        by: str = FetchTime,
        after: Optional[str] = None,
        filter: Dict[str, Any] = {},
        length: int = 1,
    ):
        rows = self.__query_rows(collection, by=by, desc=False, limit=length, after=after)
        docs = [self.__apply_projection(self.__reformResult(row), filter) for row in rows if self.__after_ok(after, row)]
        if len(docs) == 0:
            return None
        if len(docs) == 1:
            return docs[0]
        return docs

    async def range(
        self,
        collection: str,
        begin: Any,
        end: Any,
        by: str = FetchTime,
        filter: Dict[str, Any] = {},
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        rows = self.__query_rows_in_range(collection, begin=begin, end=end, by=by, limit=limit)
        docs = [self.__apply_projection(self.__reformResult(row), filter) for row in rows]
        docs.sort(key=lambda e: self.__parseFetchTime(e[Storage.FetchTime]).timestamp())
        return docs

    async def get(self, collection: str, value: Any, key: str = "_id", filter: Dict[str, Any] = {}):
        row = self.__get_one_row(collection, value=value, key=key)
        if row is None:
            return None
        return self.__apply_projection(self.__reformResult(row), filter)

    async def delete(self, collection: str, value: Any, key: str = "_id"):
        await self.__beforeModify(collection)
        table = self.__table_name(collection)
        if key == "_id":
            self.db.execute(f'DELETE FROM "{table}" WHERE _id = ?', [str(value)])
        elif key == Storage.FetchTime:
            self.db.execute(f'DELETE FROM "{table}" WHERE FetchTimeEpochUs = ?', [self.__to_epoch_us(self.__parseFetchTime(value))])
        elif key == Storage.RecordTime:
            self.db.execute(f'DELETE FROM "{table}" WHERE RecordTimeEpochUs = ?', [self.__to_epoch_us(self.__parseFetchTime(value))])
        else:
            self.db.execute(f'DELETE FROM "{table}" WHERE json_extract_string(ExtraJSON, ?) = ?', [f"$.{key}", str(value)])

    async def update(self, collection: str, id: str, value: Dict[str, Any]):
        await self.__beforeModify(collection)
        row = self.__get_one_row(collection, value=id, key="_id")
        if row is None:
            return
        table = self.__table_name(collection)
        data = row["Data"]
        extra = row["Extra"]
        record_epoch = row["RecordTimeEpochUs"]
        fetch_epoch = row["FetchTimeEpochUs"]
        for k, v in value.items():
            if k == Storage.Data:
                data = v
            elif k == Storage.RecordTime:
                record_epoch = self.__to_epoch_us(self.__parseFetchTime(v))
            elif k == Storage.FetchTime:
                fetch_epoch = self.__to_epoch_us(self.__parseFetchTime(v))
            else:
                extra[k] = v
        self.db.execute(
            f"""
            UPDATE "{table}"
            SET RecordTimeEpochUs = ?, FetchTimeEpochUs = ?, DataJSON = ?, ExtraJSON = ?
            WHERE _id = ?
            """,
            [record_epoch, fetch_epoch, json.dumps(data, ensure_ascii=True), json.dumps(extra, ensure_ascii=True), id],
        )

    @staticmethod
    def _load_timezone(tz_name: str):
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return ZoneInfo(tz_name.upper())

    @staticmethod
    def __to_epoch_us(dt: datetime) -> int:
        return int(round(dt.timestamp() * 1_000_000))

    def __table_name(self, collection: str) -> str:
        return f"Storage_{collection}"

    def __parseFetchTime(self, fetchTime: Any) -> datetime:
        if isinstance(fetchTime, int):
            return datetime.fromtimestamp(fetchTime / 1000.0, tz=self.tz)
        if isinstance(fetchTime, float):
            return datetime.fromtimestamp(fetchTime, tz=self.tz)
        if isinstance(fetchTime, str):
            dt = datetime.fromisoformat(fetchTime)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=self.tz)
            return dt
        if isinstance(fetchTime, datetime):
            if fetchTime.tzinfo is None:
                return fetchTime.replace(tzinfo=self.tz)
            return fetchTime
        raise RuntimeError("FetchTime not recognized.")

    def __epoch_us_to_iso(self, epoch_us: int) -> str:
        dt_utc = datetime.fromtimestamp(epoch_us / 1_000_000, tz=ZoneInfo("UTC"))
        return dt_utc.astimezone(self.tz).isoformat()

    async def __senseExistCollections(self):
        rows = self.db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()").fetchall()
        names = [r[0] for r in rows]
        self.existCollections = [name[8:] for name in names if name.startswith("Storage_")]

    async def __beforeModify(self, collection: str):
        if self.existCollections is None:
            await self.__senseExistCollections()
        if collection not in self.existCollections:
            table = self.__table_name(collection)
            self.db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS "{table}" (
                    _id TEXT PRIMARY KEY,
                    RecordTimeEpochUs BIGINT NOT NULL,
                    FetchTimeEpochUs BIGINT NOT NULL,
                    DataJSON TEXT NOT NULL,
                    ExtraJSON TEXT NOT NULL
                )
                """
            )
            self.db.execute(f'CREATE INDEX IF NOT EXISTS "{table}_fetch_idx" ON "{table}" (FetchTimeEpochUs)')
            self.db.execute(f'CREATE INDEX IF NOT EXISTS "{table}_record_idx" ON "{table}" (RecordTimeEpochUs)')
            self.existCollections.append(collection)

    def __reformResult(self, result_row: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "_id": result_row["_id"],
            Storage.RecordTime: self.__epoch_us_to_iso(result_row["RecordTimeEpochUs"]),
            Storage.FetchTime: self.__epoch_us_to_iso(result_row["FetchTimeEpochUs"]),
            Storage.Data: result_row["Data"],
        }
        result.update(result_row["Extra"])
        return result

    @staticmethod
    def __set_nested(doc: Dict[str, Any], path: List[str], value: Any):
        node = doc
        for key in path[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[path[-1]] = value

    @staticmethod
    def __extract_nested(doc: Dict[str, Any], path: List[str]):
        node: Any = doc
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return False, None
            node = node[key]
        return True, node

    def __apply_projection(self, doc: Dict[str, Any], projection: Dict[str, Any]) -> Dict[str, Any]:
        if projection == {}:
            return doc
        projected: Dict[str, Any] = {}
        for key, include in projection.items():
            if not include:
                continue
            path = key.split(".")
            ok, value = self.__extract_nested(doc, path)
            if ok:
                self.__set_nested(projected, path, value)
        return projected

    def __after_ok(self, after: Optional[str], row: Dict[str, Any]) -> bool:
        if not after:
            return True
        return self.__to_epoch_us(self.__parseFetchTime(after)) < row["FetchTimeEpochUs"]

    def __read_rows(self, table: str, query: str, params: List[Any]) -> List[Dict[str, Any]]:
        rows = self.db.execute(query, params).fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "_id": row[0],
                    "RecordTimeEpochUs": int(row[1]),
                    "FetchTimeEpochUs": int(row[2]),
                    "Data": json.loads(row[3]),
                    "Extra": json.loads(row[4]),
                }
            )
        return result

    def __query_rows(self, collection: str, by: str, desc: bool, limit: int, after: Optional[str]) -> List[Dict[str, Any]]:
        table = self.__table_name(collection)
        order = "DESC" if desc else "ASC"
        if by == Storage.FetchTime:
            if after:
                return self.__read_rows(
                    table,
                    f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" WHERE FetchTimeEpochUs > ? ORDER BY FetchTimeEpochUs {order} LIMIT ?',
                    [self.__to_epoch_us(self.__parseFetchTime(after)), int(limit)],
                )
            return self.__read_rows(
                table,
                f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" ORDER BY FetchTimeEpochUs {order} LIMIT ?',
                [int(limit)],
            )
        if by == Storage.RecordTime:
            if after:
                return self.__read_rows(
                    table,
                    f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" WHERE RecordTimeEpochUs > ? ORDER BY RecordTimeEpochUs {order} LIMIT ?',
                    [self.__to_epoch_us(self.__parseFetchTime(after)), int(limit)],
                )
            return self.__read_rows(
                table,
                f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" ORDER BY RecordTimeEpochUs {order} LIMIT ?',
                [int(limit)],
            )
        rows = self.__read_rows(
            table,
            f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}"',
            [],
        )
        rows.sort(key=lambda r: self.__reformResult(r).get(by), reverse=desc)
        if after:
            rows = [r for r in rows if self.__after_ok(after, r)]
        return rows[:limit]

    def __query_rows_in_range(self, collection: str, begin: Any, end: Any, by: str, limit: int) -> List[Dict[str, Any]]:
        table = self.__table_name(collection)
        if by == Storage.FetchTime:
            return self.__read_rows(
                table,
                f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" WHERE FetchTimeEpochUs > ? AND FetchTimeEpochUs < ? LIMIT ?',
                [self.__to_epoch_us(self.__parseFetchTime(begin)), self.__to_epoch_us(self.__parseFetchTime(end)), int(limit)],
            )
        if by == Storage.RecordTime:
            return self.__read_rows(
                table,
                f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" WHERE RecordTimeEpochUs > ? AND RecordTimeEpochUs < ? LIMIT ?',
                [self.__to_epoch_us(self.__parseFetchTime(begin)), self.__to_epoch_us(self.__parseFetchTime(end)), int(limit)],
            )
        rows = self.__read_rows(
            table,
            f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}"',
            [],
        )
        docs = [self.__reformResult(r) for r in rows]
        result = []
        for i, doc in enumerate(docs):
            v = doc.get(by)
            if v is not None and begin < v < end:
                result.append(rows[i])
        return result[:limit]

    def __get_one_row(self, collection: str, value: Any, key: str) -> Optional[Dict[str, Any]]:
        table = self.__table_name(collection)
        if key == "_id":
            rows = self.__read_rows(
                table,
                f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" WHERE _id = ? LIMIT 1',
                [str(value)],
            )
            return rows[0] if len(rows) > 0 else None
        if key == Storage.FetchTime:
            rows = self.__read_rows(
                table,
                f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" WHERE FetchTimeEpochUs = ? LIMIT 1',
                [self.__to_epoch_us(self.__parseFetchTime(value))],
            )
            return rows[0] if len(rows) > 0 else None
        if key == Storage.RecordTime:
            rows = self.__read_rows(
                table,
                f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}" WHERE RecordTimeEpochUs = ? LIMIT 1',
                [self.__to_epoch_us(self.__parseFetchTime(value))],
            )
            return rows[0] if len(rows) > 0 else None
        rows = self.__read_rows(
            table,
            f'SELECT _id, RecordTimeEpochUs, FetchTimeEpochUs, DataJSON, ExtraJSON FROM "{table}"',
            [],
        )
        for row in rows:
            doc = self.__reformResult(row)
            if doc.get(key) == value:
                return row
        return None
