"""Generic traceability service — builds trace chains from station_links dynamically."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generic_record import GenericRecord, GenericRecordItem
from app.models.station import Station, StationLink, StationSchema


class TraceNode:
    """One node in a traceability chain."""

    __slots__ = ("station_code", "station_name", "record", "items", "schema")

    def __init__(
        self,
        station_code: str,
        station_name: str,
        record: GenericRecord | None,
        items: list[GenericRecordItem],
        schema: StationSchema | None,
    ):
        self.station_code = station_code
        self.station_name = station_name
        self.record = record
        self.items = items
        self.schema = schema

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_code": self.station_code,
            "station_name": self.station_name,
            "record": _record_dict(self.record) if self.record else None,
            "items": [_item_dict(i) for i in self.items],
        }


class GenericTraceabilityService:
    """Builds N-level trace chains from ``station_links`` instead of hardcoded P3->P2->P1."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_chain(
        self,
        tenant_id: UUID,
        lot_no_norm: int,
        start_station_code: str | None = None,
    ) -> list[TraceNode]:
        """Walk the station_links graph from *start_station_code* (default: highest sort_order)
        and collect records for each station along the trace.

        Returns a list of ``TraceNode`` ordered from the starting station back to the origin.
        """
        stations = await self._load_stations(tenant_id)
        links = await self._load_links(tenant_id)
        schemas = await self._load_schemas(tenant_id)

        if not stations:
            return []

        station_by_id = {s.id: s for s in stations}
        station_by_code = {s.code: s for s in stations}

        # Determine start
        if start_station_code and start_station_code in station_by_code:
            start = station_by_code[start_station_code]
        else:
            start = max(stations, key=lambda s: s.sort_order)

        # Build adjacency: from_station_id -> [(to_station_id, link)]
        adj: dict[UUID, list[tuple[UUID, StationLink]]] = defaultdict(list)
        for lnk in links:
            adj[lnk.from_station_id].append((lnk.to_station_id, lnk))

        # Walk the graph (simple DFS, expecting a chain, not a DAG)
        visited: set[UUID] = set()
        chain: list[TraceNode] = []
        current_station = start
        current_lot = lot_no_norm

        while current_station and current_station.id not in visited:
            visited.add(current_station.id)

            record, items = await self._fetch_record(
                tenant_id, current_station.id, current_lot
            )

            schema = schemas.get(current_station.id)

            chain.append(
                TraceNode(
                    station_code=current_station.code,
                    station_name=current_station.name,
                    record=record,
                    items=items,
                    schema=schema,
                )
            )

            # Follow outgoing link
            next_links = adj.get(current_station.id, [])
            if not next_links:
                break

            to_id, link = next_links[0]
            current_station = station_by_id.get(to_id)

            # If the link has a shared_key, lot_no_norm carries over.
            # For more complex link_config (field-to-field matching), the
            # lot_no_norm stays the same (simplification for Phase 2).

        return chain

    async def flatten_for_analytics(
        self,
        tenant_id: UUID,
        records: list[GenericRecord],
        mapping: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Flatten records according to analytics_mappings.

        *mapping* is a list of ``{"source_path": ..., "output_column": ...}`` dicts.
        """
        result: list[dict[str, Any]] = []
        for rec in records:
            row: dict[str, Any] = {}
            for m in mapping:
                row[m["output_column"]] = _extract_path(rec.data, m["source_path"])
            result.append(row)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_stations(self, tenant_id: UUID) -> list[Station]:
        res = await self.session.execute(
            select(Station)
            .where(Station.tenant_id == tenant_id)
            .order_by(Station.sort_order)
        )
        return list(res.scalars().all())

    async def _load_links(self, tenant_id: UUID) -> list[StationLink]:
        res = await self.session.execute(
            select(StationLink)
            .where(StationLink.tenant_id == tenant_id)
            .order_by(StationLink.sort_order)
        )
        return list(res.scalars().all())

    async def _load_schemas(self, tenant_id: UUID) -> dict[UUID, StationSchema]:
        res = await self.session.execute(
            select(StationSchema).where(StationSchema.is_active == True)
        )
        return {s.station_id: s for s in res.scalars().all()}

    async def _fetch_record(
        self, tenant_id: UUID, station_id: UUID, lot_no_norm: int
    ) -> tuple[GenericRecord | None, list[GenericRecordItem]]:
        res = await self.session.execute(
            select(GenericRecord).where(
                GenericRecord.tenant_id == tenant_id,
                GenericRecord.station_id == station_id,
                GenericRecord.lot_no_norm == lot_no_norm,
            )
        )
        record = res.scalar_one_or_none()
        if not record:
            return None, []

        items_res = await self.session.execute(
            select(GenericRecordItem)
            .where(GenericRecordItem.record_id == record.id)
            .order_by(GenericRecordItem.row_no)
        )
        items = list(items_res.scalars().all())
        return record, items


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------


def _extract_path(data: dict[str, Any] | None, path: str) -> Any:
    """Extract a value from a nested dict using dot-notation path."""
    if not data or not path:
        return None
    keys = path.split(".")
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _record_dict(record: GenericRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "lot_no_raw": record.lot_no_raw,
        "lot_no_norm": record.lot_no_norm,
        "data": record.data,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _item_dict(item: GenericRecordItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "row_no": item.row_no,
        "data": item.data,
    }
