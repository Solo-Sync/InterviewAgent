import pytest

from libs.storage.files import FileStore


def test_path_for_accepts_safe_flat_key(tmp_path) -> None:
    store = FileStore(str(tmp_path / "store"))

    path = store.path_for("answer-01.wav")

    assert path == store.root / "answer-01.wav"


@pytest.mark.parametrize(
    "key",
    [
        "../../backend/.env",
        "/tmp/secret.wav",
        "nested/audio.wav",
        r"..\\windows\\secret.wav",
    ],
)
def test_path_for_rejects_unsafe_keys(tmp_path, key: str) -> None:
    store = FileStore(str(tmp_path / "store"))

    with pytest.raises(ValueError, match="invalid storage key"):
        store.path_for(key)


def test_path_for_rejects_symlink_that_escapes_store(tmp_path) -> None:
    store = FileStore(str(tmp_path / "store"))
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"secret")
    symlink_path = store.root / "link.wav"
    try:
        symlink_path.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink unsupported: {exc}")

    with pytest.raises(ValueError, match="invalid storage key"):
        store.path_for("link.wav")
