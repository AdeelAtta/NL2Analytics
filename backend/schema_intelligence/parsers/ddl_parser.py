from __future__ import annotations

import sqlglot
import sqlglot.expressions as exp

from schema_intelligence.connectors.base import (
    ExtractedColumn,
    ExtractedTable,
    ForeignKeyRef,
)


class DDLError(Exception):
    ...


class DDLParser:
    def __init__(self, dialect: str = "postgres") -> None:
        self.dialect = dialect

    def parse(self, ddl: str) -> list[ExtractedTable]:
        try:
            raw = sqlglot.parse(ddl, dialect=self.dialect)
        except Exception as e:
            raise DDLError(f"sqlglot parse error: {e}") from e

        if not raw:
            return []

        stmts = [s for s in raw if s is not None]

        tables: list[ExtractedTable] = []
        table_comments: dict[str, str] = {}
        column_comments: dict[tuple[str, str], str] = {}

        for s in stmts:
            if isinstance(s, exp.Create) and self._is_create_table(s):
                t_ = self._extract_table(s)
                if t_ is not None:
                    tables.append(t_)
            elif isinstance(s, exp.Comment):
                self._extract_comment(s, table_comments, column_comments)

        for table in tables:
            if table.name in table_comments:
                table.comment = table_comments[table.name]
            for col in table.columns:
                key = (table.name, col.name)
                if key in column_comments:
                    col.comment = column_comments[key]

        return tables

    def parse_single(self, ddl: str) -> ExtractedTable | None:
        tables = self.parse(ddl)
        return tables[0] if tables else None

    def _is_create_table(self, create: exp.Create) -> bool:
        kind = create.kind
        if isinstance(kind, str):
            return kind.upper() == "TABLE"
        if isinstance(kind, exp.Var):
            return kind.name.upper() == "TABLE"
        return False

    def _extract_table(self, create: exp.Create) -> ExtractedTable | None:
        schema = create.this
        if not isinstance(schema, exp.Schema):
            return None

        table_name = self._name_of(schema.this)
        if table_name is None:
            return None

        columns: list[ExtractedColumn] = []
        pk_set: set[str] = set()
        fks: dict[str, ForeignKeyRef] = {}

        for child in schema.expressions:
            if isinstance(child, exp.ColumnDef):
                col = self._extract_column(child)
                if col is not None:
                    columns.append(col)
            elif isinstance(child, exp.PrimaryKey):
                for c in child.expressions:
                    if isinstance(c, exp.Identifier):
                        pk_set.add(c.name)
            elif isinstance(child, exp.ForeignKey):
                self._extract_fk(child, fks)

        col_by_name = {c.name: c for c in columns}
        for pk_name in pk_set:
            if pk_name in col_by_name:
                col_by_name[pk_name].is_primary_key = True
        for fk_name, fk_ref in fks.items():
            if fk_name in col_by_name:
                col_by_name[fk_name].foreign_key = fk_ref

        ddl = create.sql(dialect=self.dialect)

        return ExtractedTable(
            name=table_name,
            columns=columns,
            ddl=ddl,
        )

    def _extract_column(self, col_def: exp.ColumnDef) -> ExtractedColumn | None:
        name = self._name_of(col_def.this)
        if not name:
            return None

        dtype = col_def.kind.sql(dialect=self.dialect) if col_def.kind else "unknown"

        is_nullable = True
        is_pk = False
        default: str | None = None

        for cons in col_def.constraints:
            inner = cons.kind if isinstance(cons, exp.ColumnConstraint) else cons
            if isinstance(inner, exp.NotNullColumnConstraint):
                is_nullable = inner.args.get("allow_null", False)
            elif isinstance(inner, exp.PrimaryKeyColumnConstraint):
                is_pk = True
            elif isinstance(inner, exp.DefaultColumnConstraint):
                default = inner.this.sql(dialect=self.dialect)

        return ExtractedColumn(
            name=name,
            ordinal_position=0,
            data_type=dtype,
            is_nullable=is_nullable,
            is_primary_key=is_pk,
            default_value=default,
        )

    def _extract_fk(self, fk: exp.ForeignKey, fk_map: dict[str, ForeignKeyRef]) -> None:
        ref = fk.args.get("reference")
        if ref is None or not isinstance(ref, exp.Reference):
            return

        ref_schema = ref.this
        if not isinstance(ref_schema, exp.Schema):
            return

        ref_table = self._name_of(ref_schema.this)
        if not ref_table:
            return

        ref_cols = [
            self._name_of(c) for c in ref_schema.expressions if isinstance(c, exp.Identifier)
        ]
        src_cols = [self._name_of(c) for c in fk.expressions if isinstance(c, exp.Identifier)]

        for i, src in enumerate(src_cols):
            if src:
                fk_map[src] = ForeignKeyRef(
                    ref_table=ref_table,
                    ref_column=ref_cols[i] if i < len(ref_cols) else "",
                )

    def _extract_comment(
        self,
        comment: exp.Comment,
        table_comments: dict[str, str],
        column_comments: dict[tuple[str, str], str],
    ) -> None:
        target = comment.this
        text_raw = comment.expression.sql(dialect=self.dialect) if comment.expression else ""
        text = text_raw.strip("'\"")

        if isinstance(target, exp.Table):
            table_comments[self._name_of(target)] = text
        elif isinstance(target, exp.Column):
            t_name: str | None = None
            if hasattr(target, "table") and isinstance(target.table, str):
                t_name = target.table
            elif hasattr(target, "table") and isinstance(target.table, (exp.Table, exp.Identifier)):
                t_name = self._name_of(target.table)
            c_name = self._name_of(target.this) if hasattr(target, "this") else None
            if t_name and c_name:
                column_comments[(t_name, c_name)] = text

    @staticmethod
    def _name_of(node: exp.Expression | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, exp.Identifier):
            return node.name
        if isinstance(node, (exp.Table, exp.Column)):
            return node.name
        if hasattr(node, "name") and isinstance(node.name, str):
            return node.name
        return None
