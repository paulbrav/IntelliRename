import tempfile
from pathlib import Path

from intellirename.utils import rename_file


def test_rename_file_collision() -> None:
    """Files with the same target name get suffixed on rename."""
    with tempfile.TemporaryDirectory() as temp_dir:
        first = Path(temp_dir) / "first.txt"
        second = Path(temp_dir) / "second.txt"
        first.write_text("one")
        second.write_text("two")

        rename_file(str(first), "target.txt")
        msg = rename_file(str(second), "target.txt")

        expected_path = Path(temp_dir) / "target_1.txt"
        assert expected_path.exists()
        assert "target_1.txt" in msg
