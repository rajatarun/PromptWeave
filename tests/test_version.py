import promptweave


def test_version_is_set():
    assert promptweave.__version__
    assert isinstance(promptweave.__version__, str)
