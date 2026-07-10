from __future__ import annotations

import pytest

from schema_intelligence.parsers.ddl_parser import DDLError, DDLParser


class TestDDLParserInit:
    def test_default_dialect(self) -> None:
        parser = DDLParser()
        assert parser.dialect == "postgres"

    def test_custom_dialect(self) -> None:
        parser = DDLParser(dialect="mysql")
        assert parser.dialect == "mysql"


class TestDDLParserParse:
    def test_single_column(self) -> None:
        ddl = "CREATE TABLE users (id INT);"
        tables = DDLParser().parse(ddl)
        assert len(tables) == 1
        assert tables[0].name == "users"
        assert len(tables[0].columns) == 1
        assert tables[0].columns[0].name == "id"
        assert tables[0].columns[0].data_type == "INT"
        assert tables[0].columns[0].is_nullable is True
        assert tables[0].columns[0].is_primary_key is False
        assert tables[0].columns[0].default_value is None
        assert tables[0].columns[0].foreign_key is None

    def test_multiple_columns(self) -> None:
        ddl = (
            "CREATE TABLE employees ("
            "id INT, name VARCHAR(255), salary DECIMAL(10,2), active BOOLEAN"
            ");"
        )
        tables = DDLParser().parse(ddl)
        assert len(tables) == 1
        cols = tables[0].columns
        assert len(cols) == 4
        assert cols[0].name == "id" and cols[0].data_type == "INT"
        assert cols[1].name == "name" and "VARCHAR" in cols[1].data_type.upper()
        assert cols[2].name == "salary" and "DECIMAL" in cols[2].data_type.upper()
        assert cols[3].name == "active" and "BOOL" in cols[3].data_type.upper()

    def test_not_null(self) -> None:
        ddl = "CREATE TABLE t (a INT NOT NULL, b INT NULL);"
        tables = DDLParser().parse(ddl)
        assert tables[0].columns[0].is_nullable is False
        assert tables[0].columns[1].is_nullable is True

    def test_inline_primary_key(self) -> None:
        ddl = "CREATE TABLE t (id INT PRIMARY KEY);"
        tables = DDLParser().parse(ddl)
        assert tables[0].columns[0].is_primary_key is True

    def test_table_level_primary_key(self) -> None:
        ddl = "CREATE TABLE t (a INT, b INT, PRIMARY KEY (a, b));"
        tables = DDLParser().parse(ddl)
        cols = {c.name: c for c in tables[0].columns}
        assert cols["a"].is_primary_key is True
        assert cols["b"].is_primary_key is True

    def test_foreign_key(self) -> None:
        ddl = (
            "CREATE TABLE orders ("
            "id INT, customer_id INT, FOREIGN KEY (customer_id) REFERENCES customers (id)"
            ");"
        )
        tables = DDLParser().parse(ddl)
        cols = {c.name: c for c in tables[0].columns}
        fk = cols["customer_id"].foreign_key
        assert fk is not None
        assert fk.ref_table == "customers"
        assert fk.ref_column == "id"

    def test_composite_foreign_key(self) -> None:
        ddl = (
            "CREATE TABLE line_items ("
            "order_id INT, product_id INT, "
            "FOREIGN KEY (order_id, product_id) REFERENCES order_products (o_id, p_id)"
            ");"
        )
        tables = DDLParser().parse(ddl)
        cols = {c.name: c for c in tables[0].columns}
        assert cols["order_id"].foreign_key is not None
        assert cols["order_id"].foreign_key.ref_table == "order_products"
        assert cols["order_id"].foreign_key.ref_column == "o_id"
        assert cols["product_id"].foreign_key is not None
        assert cols["product_id"].foreign_key.ref_table == "order_products"
        assert cols["product_id"].foreign_key.ref_column == "p_id"

    def test_default_value(self) -> None:
        ddl = (
            "CREATE TABLE t ("
            "a INT DEFAULT 42, b VARCHAR(50) DEFAULT 'hello', c BOOLEAN DEFAULT true"
            ");"
        )
        tables = DDLParser().parse(ddl)
        cols = {c.name: c for c in tables[0].columns}
        assert cols["a"].default_value is not None
        assert cols["b"].default_value is not None
        assert cols["c"].default_value is not None

    def test_multiple_tables(self) -> None:
        ddl = "CREATE TABLE t1 (a INT); CREATE TABLE t2 (b INT);"
        tables = DDLParser().parse(ddl)
        assert len(tables) == 2
        assert tables[0].name == "t1"
        assert tables[1].name == "t2"

    def test_schema_qualified_table(self) -> None:
        ddl = "CREATE TABLE analytics.users (id INT);"
        tables = DDLParser().parse(ddl)
        assert len(tables) == 1
        assert tables[0].name == "users"

    def test_if_not_exists(self) -> None:
        ddl = "CREATE TABLE IF NOT EXISTS t (a INT);"
        tables = DDLParser().parse(ddl)
        assert len(tables) == 1

    def test_type_with_parameters(self) -> None:
        ddl = "CREATE TABLE t (name VARCHAR(255), salary DECIMAL(10,2));"
        tables = DDLParser().parse(ddl)
        assert len(tables[0].columns) == 2
        assert "255" in tables[0].columns[0].data_type
        assert "10" in tables[0].columns[1].data_type

    def test_comment_on_table(self) -> None:
        ddl = "CREATE TABLE t (a INT); COMMENT ON TABLE t IS 'User accounts';"
        tables = DDLParser().parse(ddl)
        assert tables[0].comment == "User accounts"

    def test_comment_on_column(self) -> None:
        ddl = "CREATE TABLE t (a INT); COMMENT ON COLUMN t.a IS 'unique identifier';"
        tables = DDLParser().parse(ddl)
        assert tables[0].columns[0].comment == "unique identifier"

    def test_mixed_constraints(self) -> None:
        ddl = """
        CREATE TABLE orders (
            id BIGSERIAL PRIMARY KEY,
            user_id INT NOT NULL DEFAULT 0,
            total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
        tables = DDLParser().parse(ddl)
        cols = {c.name: c for c in tables[0].columns}
        assert len(cols) == 5
        assert cols["id"].is_primary_key is True
        assert cols["id"].is_nullable is True
        assert cols["user_id"].is_nullable is False
        assert cols["user_id"].foreign_key is not None
        assert cols["user_id"].foreign_key.ref_table == "users"
        assert cols["total"].is_nullable is False
        assert cols["total"].default_value is not None

    def test_unique_constraint_ignored(self) -> None:
        ddl = "CREATE TABLE t (a INT UNIQUE);"
        tables = DDLParser().parse(ddl)
        assert len(tables) == 1
        assert len(tables[0].columns) == 1

    def test_serial_type(self) -> None:
        ddl = "CREATE TABLE t (id SERIAL, name TEXT);"
        tables = DDLParser().parse(ddl)
        assert tables[0].columns[0].data_type.upper() == "SERIAL"

    def test_timestamptz_type(self) -> None:
        ddl = "CREATE TABLE t (ts TIMESTAMPTZ NOT NULL DEFAULT NOW());"
        tables = DDLParser().parse(ddl)
        assert "TIMESTAMPTZ" in tables[0].columns[0].data_type.upper()

    def test_empty_ddl(self) -> None:
        tables = DDLParser().parse("")
        assert tables == []

    def test_no_create_table(self) -> None:
        tables = DDLParser().parse("SELECT 1;")
        assert tables == []

    def test_whitespace_only(self) -> None:
        tables = DDLParser().parse("   \n  ")
        assert tables == []

    def test_malformed_ddl(self) -> None:
        with pytest.raises(DDLError):
            DDLParser().parse("NOT VALID SQL @@@")

    def test_ddl_preserved(self) -> None:
        ddl = "CREATE TABLE foo (id INTEGER NOT NULL, name VARCHAR(100))"
        tables = DDLParser().parse(ddl)
        assert tables[0].ddl is not None
        assert "foo" in tables[0].ddl

    def test_multiple_with_comments(self) -> None:
        ddl = """
        CREATE TABLE t1 (a INT);
        COMMENT ON TABLE t1 IS 'first table';
        CREATE TABLE t2 (b INT);
        COMMENT ON COLUMN t2.b IS 'second column';
        """
        tables = DDLParser().parse(ddl)
        assert len(tables) == 2
        tbl = {t.name: t for t in tables}
        assert tbl["t1"].comment == "first table"
        assert tbl["t2"].columns[0].comment == "second column"

    def test_inline_and_table_pk_combined(self) -> None:
        ddl = "CREATE TABLE t (id INT PRIMARY KEY, name VARCHAR(100), PRIMARY KEY (id, name));"
        tables = DDLParser().parse(ddl)
        cols = {c.name: c for c in tables[0].columns}
        assert cols["id"].is_primary_key is True
        assert cols["name"].is_primary_key is True


class TestDDLParserParseSingle:
    def test_single_table(self) -> None:
        parser = DDLParser()
        table = parser.parse_single("CREATE TABLE foo (x INT);")
        assert table is not None
        assert table.name == "foo"

    def test_empty_returns_none(self) -> None:
        parser = DDLParser()
        table = parser.parse_single("SELECT 1;")
        assert table is None

    def test_multiple_tables_returns_first(self) -> None:
        parser = DDLParser()
        table = parser.parse_single("CREATE TABLE a (x INT); CREATE TABLE b (y INT);")
        assert table is not None
        assert table.name == "a"
