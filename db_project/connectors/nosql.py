"""
db_project/connectors/nosql.py — MongoDB connector.

Kept intentionally minimal: MongoDB covers the overwhelming majority of
"NoSQL data source" needs. Extend with the same pattern (connect/disconnect/
fetch_collection/write_dataframe) if you later need Cassandra or DynamoDB.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


class MongoConnector:
    def __init__(
        self,
        host: str,
        port: int = 27017,
        database: str = "",
        username: Optional[str] = None,
        password: Optional[str] = None,
        connect_timeout: int = 30,
        label: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.connect_timeout = connect_timeout
        self.label = label or f"mongodb:{database}"
        self._client = None

    def __enter__(self) -> "MongoConnector":
        self.connect()
        return self

    def __exit__(self, *_exc) -> None:
        self.disconnect()

    def connect(self) -> None:
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("Install pymongo: pip install pymongo")
        if self.username and self.password:
            uri = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            uri = f"mongodb://{self.host}:{self.port}/{self.database}"
        self._client = MongoClient(uri, serverSelectionTimeoutMS=self.connect_timeout * 1000)
        self._client.server_info()

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def fetch_collection(self, collection: str, query: Optional[dict] = None, limit: int = 0) -> pd.DataFrame:
        self._require_connected()
        db = self._client[self.database]
        docs = list(db[collection].find(query or {}, limit=limit))
        df = pd.DataFrame(docs)
        if "_id" in df.columns:
            df["_id"] = df["_id"].astype(str)
        return df

    def write_dataframe(self, df: pd.DataFrame, collection: str, mode: str = "replace") -> int:
        """mode: 'replace' clears the collection first, 'append' inserts only."""
        self._require_connected()
        db = self._client[self.database]
        col = db[collection]
        if mode == "replace":
            col.delete_many({})
        records = df.to_dict(orient="records")
        if records:
            col.insert_many(records)
        return len(records)

    def _require_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("Not connected. Use `with MongoConnector(...) as conn:` or call connect().")
