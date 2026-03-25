"""Schema service — reads station schemas and provides validation / query helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analytics_mapping import AnalyticsMapping
from app.models.station import Station, StationLink, StationSchema
from app.models.validation_rule import ValidationRule


class SchemaService:
    """Stateless service — accepts a session per call."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Station queries
    # ------------------------------------------------------------------

    async def list_stations(self, tenant_id: UUID) -> list[Station]:
        result = await self.session.execute(
            select(Station)
            .where(Station.tenant_id == tenant_id)
            .order_by(Station.sort_order)
        )
        return list(result.scalars().all())

    async def get_station(self, tenant_id: UUID, code: str) -> Station | None:
        result = await self.session.execute(
            select(Station).where(
                Station.tenant_id == tenant_id,
                Station.code == code,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Schema queries
    # ------------------------------------------------------------------

    async def get_active_schema(
        self, tenant_id: UUID, station_code: str
    ) -> StationSchema | None:
        station = await self.get_station(tenant_id, station_code)
        if not station:
            return None
        result = await self.session.execute(
            select(StationSchema).where(
                StationSchema.station_id == station.id,
                StationSchema.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_filterable_fields(
        self, tenant_id: UUID, station_code: str
    ) -> list[dict[str, Any]]:
        schema = await self.get_active_schema(tenant_id, station_code)
        if not schema:
            return []
        return [f for f in schema.record_fields if f.get("filterable")]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def get_validation_rules(
        self, tenant_id: UUID, station_id: UUID | None = None
    ) -> list[ValidationRule]:
        stmt = select(ValidationRule).where(
            ValidationRule.tenant_id == tenant_id,
            ValidationRule.is_active == True,
        )
        if station_id is not None:
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(
                    ValidationRule.station_id == station_id,
                    ValidationRule.station_id.is_(None),
                )
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def validate_record_data(
        self,
        schema: StationSchema,
        data: dict[str, Any],
        rules: list[ValidationRule] | None = None,
    ) -> list[dict[str, str]]:
        """Validate *data* against *schema* field definitions and optional rules.

        Returns a list of ``{"field": ..., "code": ..., "message": ...}`` dicts.
        An empty list means valid.
        """
        errors: list[dict[str, str]] = []
        field_defs = {f["name"]: f for f in schema.record_fields}

        for name, fdef in field_defs.items():
            value = data.get(name)

            if fdef.get("required") and value is None:
                errors.append(
                    {"field": name, "code": "REQUIRED", "message": f"{name} is required"}
                )
                continue

            if value is None:
                continue

            ftype = fdef.get("type", "string")
            if ftype in ("integer", "float"):
                try:
                    float(value) if ftype == "float" else int(value)
                except (ValueError, TypeError):
                    errors.append(
                        {
                            "field": name,
                            "code": "INVALID_TYPE",
                            "message": f"{name} must be {ftype}",
                        }
                    )

            if "min" in fdef and value is not None:
                try:
                    if float(value) < fdef["min"]:
                        errors.append(
                            {
                                "field": name,
                                "code": "OUT_OF_RANGE",
                                "message": f"{name} below min {fdef['min']}",
                            }
                        )
                except (ValueError, TypeError):
                    pass

            if "max" in fdef and value is not None:
                try:
                    if float(value) > fdef["max"]:
                        errors.append(
                            {
                                "field": name,
                                "code": "OUT_OF_RANGE",
                                "message": f"{name} above max {fdef['max']}",
                            }
                        )
                except (ValueError, TypeError):
                    pass

        if rules:
            errors.extend(_apply_rules(rules, data))

        return errors

    # ------------------------------------------------------------------
    # Analytics mapping
    # ------------------------------------------------------------------

    async def get_analytics_mapping(
        self, tenant_id: UUID, station_id: UUID | None = None
    ) -> list[AnalyticsMapping]:
        stmt = (
            select(AnalyticsMapping)
            .where(AnalyticsMapping.tenant_id == tenant_id)
            .order_by(AnalyticsMapping.output_order)
        )
        if station_id:
            stmt = stmt.where(AnalyticsMapping.station_id == station_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Station links
    # ------------------------------------------------------------------

    async def get_station_links(self, tenant_id: UUID) -> list[StationLink]:
        result = await self.session.execute(
            select(StationLink)
            .where(StationLink.tenant_id == tenant_id)
            .order_by(StationLink.sort_order)
        )
        return list(result.scalars().all())

    # ==================================================================
    # CRUD mutations (Phase 4 — admin management)
    # ==================================================================

    # -- Station CRUD --------------------------------------------------

    async def create_station(
        self, tenant_id: UUID, code: str, name: str, sort_order: int = 0, has_items: bool = False
    ) -> Station:
        station = Station(
            tenant_id=tenant_id, code=code, name=name, sort_order=sort_order, has_items=has_items
        )
        self.session.add(station)
        await self.session.flush()
        return station

    async def update_station(
        self, tenant_id: UUID, code: str, patch: dict[str, Any]
    ) -> Station | None:
        station = await self.get_station(tenant_id, code)
        if not station:
            return None
        for k in ("name", "sort_order", "has_items"):
            if k in patch:
                setattr(station, k, patch[k])
        await self.session.flush()
        return station

    async def delete_station(self, tenant_id: UUID, code: str) -> bool:
        station = await self.get_station(tenant_id, code)
        if not station:
            return False
        await self.session.delete(station)
        await self.session.flush()
        return True

    # -- Schema CRUD ---------------------------------------------------

    async def upsert_schema(
        self,
        tenant_id: UUID,
        station_code: str,
        record_fields: list[dict[str, Any]],
        item_fields: list[dict[str, Any]] | None = None,
        unique_key_fields: list[str] | None = None,
        csv_signature_columns: list[str] | None = None,
        csv_filename_pattern: str | None = None,
        csv_field_mapping: dict[str, Any] | None = None,
    ) -> StationSchema | None:
        station = await self.get_station(tenant_id, station_code)
        if not station:
            return None

        existing = await self.get_active_schema(tenant_id, station_code)
        if existing:
            existing.record_fields = record_fields
            existing.item_fields = item_fields
            existing.unique_key_fields = unique_key_fields or existing.unique_key_fields
            existing.csv_signature_columns = csv_signature_columns
            existing.csv_filename_pattern = csv_filename_pattern
            existing.csv_field_mapping = csv_field_mapping
            await self.session.flush()
            return existing

        schema = StationSchema(
            station_id=station.id,
            version=1,
            is_active=True,
            record_fields=record_fields,
            item_fields=item_fields,
            unique_key_fields=unique_key_fields or [],
            csv_signature_columns=csv_signature_columns,
            csv_filename_pattern=csv_filename_pattern,
            csv_field_mapping=csv_field_mapping,
        )
        self.session.add(schema)
        await self.session.flush()
        return schema

    # -- Validation Rule CRUD ------------------------------------------

    async def create_validation_rule(
        self, tenant_id: UUID, station_id: UUID | None, field_name: str,
        rule_type: str, rule_config: dict[str, Any],
    ) -> ValidationRule:
        rule = ValidationRule(
            tenant_id=tenant_id, station_id=station_id, field_name=field_name,
            rule_type=rule_type, rule_config=rule_config,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def update_validation_rule(
        self, rule_id: UUID, patch: dict[str, Any]
    ) -> ValidationRule | None:
        result = await self.session.execute(
            select(ValidationRule).where(ValidationRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            return None
        for k in ("field_name", "rule_type", "rule_config", "is_active"):
            if k in patch:
                setattr(rule, k, patch[k])
        await self.session.flush()
        return rule

    async def delete_validation_rule(self, rule_id: UUID) -> bool:
        result = await self.session.execute(
            select(ValidationRule).where(ValidationRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            return False
        await self.session.delete(rule)
        await self.session.flush()
        return True

    # -- Analytics Mapping CRUD ----------------------------------------

    async def create_analytics_mapping(
        self, tenant_id: UUID, station_id: UUID, source_path: str,
        output_column: str, output_order: int, data_type: str = "string",
        null_if_missing: bool = True,
    ) -> AnalyticsMapping:
        mapping = AnalyticsMapping(
            tenant_id=tenant_id, station_id=station_id, source_path=source_path,
            output_column=output_column, output_order=output_order,
            data_type=data_type, null_if_missing=null_if_missing,
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def update_analytics_mapping(
        self, mapping_id: UUID, patch: dict[str, Any]
    ) -> AnalyticsMapping | None:
        result = await self.session.execute(
            select(AnalyticsMapping).where(AnalyticsMapping.id == mapping_id)
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            return None
        for k in ("source_path", "output_column", "output_order", "data_type", "null_if_missing"):
            if k in patch:
                setattr(mapping, k, patch[k])
        await self.session.flush()
        return mapping

    async def delete_analytics_mapping(self, mapping_id: UUID) -> bool:
        result = await self.session.execute(
            select(AnalyticsMapping).where(AnalyticsMapping.id == mapping_id)
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            return False
        await self.session.delete(mapping)
        await self.session.flush()
        return True

    # -- Station Link CRUD ---------------------------------------------

    async def create_station_link(
        self, tenant_id: UUID, from_station_id: UUID, to_station_id: UUID,
        link_type: str, link_config: dict[str, Any] | None = None, sort_order: int = 0,
    ) -> StationLink:
        link = StationLink(
            tenant_id=tenant_id, from_station_id=from_station_id,
            to_station_id=to_station_id, link_type=link_type,
            link_config=link_config or {}, sort_order=sort_order,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def update_station_link(
        self, link_id: UUID, patch: dict[str, Any]
    ) -> StationLink | None:
        result = await self.session.execute(
            select(StationLink).where(StationLink.id == link_id)
        )
        link = result.scalar_one_or_none()
        if not link:
            return None
        for k in ("link_type", "link_config", "sort_order"):
            if k in patch:
                setattr(link, k, patch[k])
        await self.session.flush()
        return link

    async def delete_station_link(self, link_id: UUID) -> bool:
        result = await self.session.execute(
            select(StationLink).where(StationLink.id == link_id)
        )
        link = result.scalar_one_or_none()
        if not link:
            return False
        await self.session.delete(link)
        await self.session.flush()
        return True


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _apply_rules(
    rules: list[ValidationRule], data: dict[str, Any]
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for rule in rules:
        value = data.get(rule.field_name)
        cfg = rule.rule_config or {}

        if rule.rule_type == "required" and value is None:
            errors.append(
                {
                    "field": rule.field_name,
                    "code": "REQUIRED",
                    "message": f"{rule.field_name} is required",
                }
            )

        elif rule.rule_type == "enum" and value is not None:
            allowed = cfg.get("values", [])
            if value not in allowed:
                errors.append(
                    {
                        "field": rule.field_name,
                        "code": "INVALID_ENUM",
                        "message": f"{rule.field_name} must be one of {allowed}",
                    }
                )

        elif rule.rule_type == "range" and value is not None:
            try:
                v = float(value)
                lo, hi = cfg.get("min"), cfg.get("max")
                if lo is not None and v < lo:
                    errors.append(
                        {
                            "field": rule.field_name,
                            "code": "OUT_OF_RANGE",
                            "message": f"{rule.field_name} below min {lo}",
                        }
                    )
                if hi is not None and v > hi:
                    errors.append(
                        {
                            "field": rule.field_name,
                            "code": "OUT_OF_RANGE",
                            "message": f"{rule.field_name} above max {hi}",
                        }
                    )
            except (ValueError, TypeError):
                pass

        elif rule.rule_type == "regex" and value is not None:
            import re

            pattern = cfg.get("pattern", "")
            if pattern and not re.match(pattern, str(value)):
                errors.append(
                    {
                        "field": rule.field_name,
                        "code": "INVALID_FORMAT",
                        "message": f"{rule.field_name} does not match pattern {pattern}",
                    }
                )

    return errors
