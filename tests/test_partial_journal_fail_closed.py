"""Regression: an interrupted journal initialization must never pass startup gate."""

import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from agency import fenced_unit_journal
from agency import fenced_startup_gate


class PartialJournalFailClosedTests(unittest.TestCase):
    def test_schema_creation_failure_leaves_unstartable_journal(self):
        with tempfile.TemporaryDirectory(prefix="hermes-partial-journal-") as directory:
            path = pathlib.Path(directory) / "owned-units.sqlite"
            original_connect = sqlite3.connect

            class FailingConnection:
                def __init__(self, connection):
                    self.connection = connection

                def execute(self, statement, *args, **kwargs):
                    if "CREATE TABLE" in statement:
                        raise sqlite3.OperationalError("injected schema failure")
                    return self.connection.execute(statement, *args, **kwargs)

                def close(self):
                    self.connection.close()

            def failing_connect(*args, **kwargs):
                return FailingConnection(original_connect(*args, **kwargs))

            with patch.object(fenced_unit_journal.sqlite3, "connect", side_effect=failing_connect):
                with self.assertRaisesRegex(sqlite3.OperationalError, "injected schema failure"):
                    fenced_unit_journal._connect(str(path))

            self.assertTrue(path.is_file())
            with patch.object(fenced_startup_gate.os, "geteuid", return_value=0):
                with self.assertRaises(sqlite3.DatabaseError):
                    fenced_startup_gate.require_recovered(str(path))


if __name__ == "__main__":
    unittest.main()
