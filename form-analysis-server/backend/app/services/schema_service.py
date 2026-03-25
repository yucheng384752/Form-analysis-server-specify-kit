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
