import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import load_dotenv


class DotenvTests(unittest.TestCase):
    def write_env(self, contents):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / ".env"
        path.write_text(contents, encoding="utf-8")
        return directory, path

    def test_loads_google_and_aws_credentials(self):
        directory, path = self.write_env(
            "GOOGLE_CLOUD_API_KEY='google-test'\n"
            "AWS_ACCESS_KEY_ID=aws-test\n"
            'AWS_SECRET_ACCESS_KEY="secret-test"\n'
        )
        self.addCleanup(directory.cleanup)
        with patch.dict(os.environ, {}, clear=True):
            load_dotenv(path)
            self.assertEqual(os.environ["GOOGLE_CLOUD_API_KEY"], "google-test")
            self.assertEqual(os.environ["AWS_ACCESS_KEY_ID"], "aws-test")
            self.assertEqual(os.environ["AWS_SECRET_ACCESS_KEY"], "secret-test")

    def test_does_not_override_existing_environment(self):
        directory, path = self.write_env("GOOGLE_CLOUD_API_KEY=file-value\n")
        self.addCleanup(directory.cleanup)
        with patch.dict(os.environ, {"GOOGLE_CLOUD_API_KEY": "server-value"}, clear=True):
            load_dotenv(path)
            self.assertEqual(os.environ["GOOGLE_CLOUD_API_KEY"], "server-value")

    def test_missing_file_is_allowed(self):
        load_dotenv(Path("does-not-exist.env"))


if __name__ == "__main__":
    unittest.main()
