def test_fastapi_import() -> None:
    import fastapi  # noqa: F811

    assert fastapi.__version__


def test_pydantic_import() -> None:
    import pydantic  # noqa: F811

    assert pydantic.__version__


def test_pydantic_settings_import() -> None:
    import pydantic_settings  # noqa: F811

    assert pydantic_settings.__version__


def test_structlog_import() -> None:
    import structlog  # noqa: F811

    assert structlog.__version__


def test_sqlalchemy_import() -> None:
    import sqlalchemy  # noqa: F811

    assert sqlalchemy.__version__


def test_alembic_import() -> None:
    import alembic  # noqa: F811

    assert alembic.__version__


def test_httpx_import() -> None:
    import httpx  # noqa: F811

    assert httpx.__version__


def test_asyncpg_import() -> None:
    import asyncpg  # noqa: F811

    assert asyncpg.__version__


def test_python_jose_import() -> None:
    import jose  # noqa: F811

    assert jose.__version__


def test_passlib_import() -> None:
    import passlib  # noqa: F811

    assert passlib.__version__
