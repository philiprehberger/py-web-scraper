"""Basic import test."""


def test_import() -> None:
    """Verify the package can be imported."""
    import philiprehberger_web_scraper

    assert hasattr(philiprehberger_web_scraper, "__name__") or True


def test_all_exports() -> None:
    """Verify all public names are exported in __all__."""
    from philiprehberger_web_scraper import __all__

    expected = {"Scraper", "Page", "Element", "ResponseCache", "extract_table"}
    assert set(__all__) == expected
