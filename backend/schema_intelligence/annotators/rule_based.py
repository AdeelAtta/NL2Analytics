from __future__ import annotations

import re
from typing import ClassVar

from schema_intelligence.annotators.base import (
    AnnotatedColumn,
    AnnotationResult,
    BaseAnnotator,
)
from schema_intelligence.connectors.base import ExtractedColumn, ExtractedTable


class RuleBasedAnnotator(BaseAnnotator):
    _COLUMN_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (re.compile(r"^(id|uid|uuid)(_\w+)?$", re.I), "Unique identifier for this {context}."),
        (re.compile(r"^(\w+)_id$"), "Foreign key referencing the associated {group}. Identifies the related {group} record."),
        (re.compile(r"^created_at$", re.I), "Timestamp when the record was created."),
        (re.compile(r"^updated_at$", re.I), "Timestamp when the record was last updated."),
        (re.compile(r"^deleted_at$", re.I), "Timestamp when the record was soft-deleted."),
        (re.compile(r"^archived_at$", re.I), "Timestamp when the record was archived."),
        (re.compile(r"^completed_at$", re.I), "Timestamp when the process was completed."),
        (re.compile(r"^started_at$", re.I), "Timestamp when the process started."),
        (re.compile(r"^is_(\w+)", re.I), "Indicates whether this {group} is {group}."),
        (re.compile(r"^has_(\w+)", re.I), "Indicates whether this {context} has the associated {group}."),
        (re.compile(r"^(can|should|will)_(\w+)", re.I), "Flag indicating {group} permission or capability."),
        (re.compile(r"^email(_?\w+)?$", re.I), "Email address."),
        (re.compile(r"^phone(_?\w+)?$", re.I), "Phone number."),
        (re.compile(r"^(mobile|cell)(_?\w+)?$", re.I), "Mobile phone number."),
        (re.compile(r"^(first_name|fname)$", re.I), "First name."),
        (re.compile(r"^(last_name|lname|surname)$", re.I), "Last name."),
        (re.compile(r"^(full_name|display_name|name)$", re.I), "Full name or display name."),
        (re.compile(r"^username$", re.I), "Unique username for authentication."),
        (re.compile(r"^password(_?\w+)?$", re.I), "Password (stored as a secure hash)."),
        (re.compile(r"^token(_?\w+)?$", re.I), "Authentication or access token."),
        (re.compile(r"^description(_?\w+)?$", re.I), "Description or detailed notes about this {context}."),
        (re.compile(r"^summary(_?\w+)?$", re.I), "Brief summary of this {context}."),
        (re.compile(r"^title$", re.I), "Title or heading of this {context}."),
        (re.compile(r"^slug$", re.I), "URL-friendly unique identifier."),
        (re.compile(r"^code$", re.I), "Unique code or identifier for this {context}."),
        (re.compile(r"^status(_?\w+)?$", re.I), "Current status of this {context}."),
        (re.compile(r"^type(_?\w+)?$", re.I), "Type or category of this {context}."),
        (re.compile(r"^category(_?\w+)?$", re.I), "Category classification of this {context}."),
        (re.compile(r"^group(_?\w+)?$", re.I), "Group or role assignment for this {context}."),
        (re.compile(r"^role(_?\w+)?$", re.I), "Role or permission level."),
        (re.compile(r"^active$", re.I), "Indicates whether this {context} is active."),
        (re.compile(r"^enabled$", re.I), "Indicates whether this {context} is enabled."),
        (re.compile(r"^visible$", re.I), "Indicates whether this {context} is visible."),
        (re.compile(r"^(amount|price|cost|total|subtotal|fee|tax|discount)(_\w+)?$", re.I), "Monetary amount. {dtype_hint}"),
        (re.compile(r"^(quantity|count|num_?\w*)$", re.I), "Numeric count or quantity."),
        (re.compile(r"^(latitude|lat)$", re.I), "Geographic latitude coordinate."),
        (re.compile(r"^(longitude|lng|lon)$", re.I), "Geographic longitude coordinate."),
        (re.compile(r"^address(_?\w+)?$", re.I), "Street address."),
        (re.compile(r"^city$", re.I), "City name."),
        (re.compile(r"^(state|province|region)(_?\w+)?$", re.I), "State, province, or region."),
        (re.compile(r"^(zip|postal_code|postcode)$", re.I), "Postal or ZIP code."),
        (re.compile(r"^country(_?\w+)?$", re.I), "Country name or code."),
        (re.compile(r"^url(_?\w+)?$", re.I), "Uniform Resource Locator (URL)."),
        (re.compile(r"^(website|webpage)(_?\w+)?$", re.I), "Website URL."),
        (re.compile(r"^avatar(_?\w+)?$", re.I), "Avatar image URL."),
        (re.compile(r"^image(_?\w+)?$", re.I), "Image URL or path."),
        (re.compile(r"^file(_?\w+)?$", re.I), "File path or URL."),
        (re.compile(r"^(sort_order|position|priority|ordinal)$", re.I), "Ordering or sort position."),
        (re.compile(r"^(config|settings|metadata|properties|attributes|options)(_\w+)?$", re.I), "JSON configuration or metadata payload."),
        (re.compile(r"^(created_by|creator)$", re.I), "User or system that created this {context}."),
        (re.compile(r"^(updated_by|modifier)$", re.I), "User or system that last modified this {context}."),
        (re.compile(r"^(deleted_by)$", re.I), "User or system that soft-deleted this {context}."),
        (re.compile(r"^(owner|assignee|responsible)(_\w+)?$", re.I), "User or entity responsible for this {context}."),
        (re.compile(r"^(\w+)_at$", re.I), "Timestamp for the associated {group} event."),
        (re.compile(r"^(\w+)_by$", re.I), "User or system associated with the {group} action."),
    ]

    _TABLE_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (re.compile(r"^(.*_)(audit|log|history|archive)", re.I), "Historical record tracking changes to {group} entities."),
        (re.compile(r"^(.*_)(config|settings|preferences|options)", re.I), "Configuration or preference data for {group}."),
        (re.compile(r"^(.*_)(map|mapping|link|rel|bridge|junction)", re.I), "Many-to-many relationship mapping between {group} entities."),
        (re.compile(r"^(.*_)(lookup|ref|reference|codelist|enum)", re.I), "Reference or lookup data for {group}."),
        (re.compile(r"^(.*_)(draft|temp|tmp|staging)", re.I), "Temporary or draft data for {group}."),
        (re.compile(r"^(.*_)(stats|statistics|metrics|agg|summary)", re.I), "Aggregated statistics or metrics for {group}."),
    ]

    async def annotate(self, table: ExtractedTable) -> AnnotationResult:
        desc = table.comment or self._describe_table(table)
        columns = [self._describe_column(c, table.name) for c in table.columns]
        return AnnotationResult(
            table_name=table.name,
            table_description=desc,
            columns=columns,
        )

    async def annotate_batch(
        self, tables: list[ExtractedTable]
    ) -> list[AnnotationResult]:
        return [await self.annotate(t) for t in tables]

    def _describe_table(self, table: ExtractedTable) -> str:
        name = table.name
        pk_count = sum(1 for c in table.columns if c.is_primary_key)
        fk_count = sum(1 for c in table.columns if c.foreign_key is not None)
        nullable_count = sum(1 for c in table.columns if c.is_nullable)
        has_monetary = any(
            c.name.lower() in ("amount", "price", "cost", "total", "fee", "tax")
            for c in table.columns
        )
        has_timestamps = any(
            c.name.lower() in ("created_at", "updated_at", "deleted_at")
            for c in table.columns
        )
        has_json = any(
            c.name.lower() in ("config", "settings", "metadata", "properties")
            for c in table.columns
        )

        for pattern, template in self._TABLE_PATTERNS:
            m = pattern.match(name)
            if m:
                group = m.group(1).rstrip("_") if m.lastindex and m.group(1) else name
                context = self._natural_name(group or name)
                return template.format(group=context)

        parts: list[str] = []
        if pk_count == 1 and fk_count > 0:
            parts.append("Reference table")
        elif fk_count > 2:
            parts.append("Relationship junction")
        elif has_monetary:
            parts.append("Financial transaction")
        elif has_json:
            parts.append("Configuration or metadata")
        else:
            parts.append("Stores information")

        target = self._natural_name(name)
        parts.append(f"about {target}")

        if has_timestamps:
            parts.append("with timestamp tracking")
        if not nullable_count and len(table.columns) > 1:
            parts.append("(all fields required)")

        desc = " ".join(parts)
        return desc[0].upper() + desc[1:] + "."

    def _describe_column(
        self, col: ExtractedColumn, table_name: str
    ) -> AnnotatedColumn:
        if col.comment:
            return AnnotatedColumn(name=col.name, description=col.comment)

        context = self._natural_name(table_name)
        hint = self._dtype_hint(col)
        desc = self._apply_name_pattern(col.name, context, hint)
        parts: list[str] = []

        if col.foreign_key:
            fk = col.foreign_key
            parts.append(
                f"Foreign key referencing {fk.ref_table}.{fk.ref_column}."
            )

        parts.append(desc)

        if "Foreign key" not in parts[0] and col.foreign_key:
            fk = col.foreign_key
            parts.insert(
                0,
                f"Foreign key referencing {fk.ref_table}.{fk.ref_column}.",
            )

        if not col.is_nullable:
            parts.append("Required. Cannot be null.")

        if col.is_primary_key:
            parts.append("Primary key.")

        if col.default_value is not None:
            parts.append(f"Defaults to {col.default_value}.")

        description = " ".join(parts) if parts else desc
        return AnnotatedColumn(name=col.name, description=description)

    def _apply_name_pattern(self, col_name: str, context: str, dtype_hint: str = "") -> str:
        for pattern, template in self._COLUMN_PATTERNS:
            m = pattern.match(col_name)
            if m:
                group = ""
                if m.lastindex and m.lastindex >= 1:
                    group = self._natural_name(m.group(1))
                formatted = template.format(
                    dtype_hint=dtype_hint,
                    context=context,
                    group=group or "",
                )
                if formatted and formatted[0].islower():
                    formatted = formatted[0].upper() + formatted[1:]
                return formatted
        natural = self._natural_name(col_name)
        return f"{natural}."

    @staticmethod
    def _natural_name(name: str) -> str:
        s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
        s = re.sub(r"[_\-\s]+", " ", s)
        s = s.strip().lower()
        return s

    @staticmethod
    def _dtype_hint(col: ExtractedColumn) -> str:
        dt = col.data_type.upper()
        if dt in ("INT", "INTEGER", "BIGINT", "SMALLINT", "SERIAL", "BIGSERIAL"):
            if col.character_max_length:
                return f"Maximum {col.character_max_length} characters."
            return ""
        if "VARCHAR" in dt or "CHAR" in dt or "TEXT" in dt:
            if col.character_max_length:
                return f"Maximum {col.character_max_length} characters."
            return "Variable-length text."
        if "DECIMAL" in dt or "NUMERIC" in dt or "FLOAT" in dt or "REAL" in dt or "DOUBLE" in dt:
            if col.numeric_precision is not None and col.numeric_scale is not None:
                return f"Precision {col.numeric_precision}, scale {col.numeric_scale}."
            return "Decimal numeric value."
        if "BOOL" in dt:
            return "Boolean true/false value."
        if "DATE" in dt and "TIME" in dt:
            return "Timestamp with timezone." if "TZ" in dt else "Timestamp value."
        if "DATE" in dt:
            return "Date value."
        if "TIME" in dt and "TZ" in dt:
            return "Time value with timezone."
        if "TIME" in dt:
            return "Time value."
        if "JSON" in dt or "JSONB" in dt:
            return "JSON structured data."
        if "UUID" in dt:
            return "Universally unique identifier."
        if "ARRAY" in dt:
            return "Array of values."
        if "BYTES" in dt or "BLOB" in dt or "BINARY" in dt:
            return "Binary data."
        return ""
