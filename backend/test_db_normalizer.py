import unittest
from database import UnifiedRow, QueryNormalizerCursor, DBIntegrityError

class MockRawCursor:
    def __init__(self):
        self.last_query = None
        self.last_params = None
        self.description = [('id', 3), ('name', 253), ('email', 253)]
        self.rows = [(1, 'John Doe', 'john@example.com')]

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        return self

    def executemany(self, query, seq_of_params):
        self.last_query = query
        self.last_params = seq_of_params
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class TestDBNormalizer(unittest.TestCase):
    def test_mysql_row_access(self):
        raw_tuple = (42, 'Alice', 'alice@test.com')
        desc = [('id', 3), ('name', 253), ('email', 253)]
        row = UnifiedRow(raw_tuple, desc)

        # Index access
        self.assertEqual(row[0], 42)
        self.assertEqual(row[1], 'Alice')

        # Case-sensitive key access
        self.assertEqual(row['id'], 42)
        self.assertEqual(row['name'], 'Alice')

        # Case-insensitive key access
        self.assertEqual(row['ID'], 42)
        self.assertEqual(row['Name'], 'Alice')
        self.assertEqual(row['email'], 'alice@test.com')

        # Dict conversion
        row_dict = dict(row)
        self.assertEqual(row_dict, {'id': 42, 'name': 'Alice', 'email': 'alice@test.com'})

        # Unpacking
        val_id, val_name, val_email = row
        self.assertEqual(val_id, 42)
        self.assertEqual(val_name, 'Alice')

    def test_query_normalization_sqlite(self):
        mock_cursor = MockRawCursor()
        normalizer = QueryNormalizerCursor(mock_cursor, 'sqlite')

        # Replace %s with ?
        normalizer.execute("SELECT * FROM users WHERE email = %s AND id = %s", ('test@test.com', 1))
        self.assertEqual(mock_cursor.last_query, "SELECT * FROM users WHERE email = ? AND id = ?")

        # Replace RAND() with RANDOM()
        normalizer.execute("SELECT * FROM questions ORDER BY RAND()")
        self.assertEqual(mock_cursor.last_query, "SELECT * FROM questions ORDER BY RANDOM()")

    def test_query_normalization_mysql(self):
        mock_cursor = MockRawCursor()
        normalizer = QueryNormalizerCursor(mock_cursor, 'mysql')

        # Replace ? with %s
        normalizer.execute("SELECT * FROM users WHERE email = ? AND id = ?", ('test@test.com', 1))
        self.assertEqual(mock_cursor.last_query, "SELECT * FROM users WHERE email = %s AND id = %s")

        # Replace RANDOM() with RAND()
        normalizer.execute("SELECT * FROM questions ORDER BY RANDOM()")
        self.assertEqual(mock_cursor.last_query, "SELECT * FROM questions ORDER BY RAND()")

        # Ignore PRAGMA on MySQL
        mock_cursor.last_query = None
        res = normalizer.execute("PRAGMA foreign_keys = ON;")
        self.assertIs(res, normalizer)
        self.assertIsNone(mock_cursor.last_query)  # Not called


if __name__ == '__main__':
    unittest.main()
