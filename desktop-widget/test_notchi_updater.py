import hashlib
import io
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import notchi_updater as updater


def package():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("Notchi.exe", b"MZ synthetic test executable")
        archive.writestr("../outside.txt", b"never extract this")
    return output.getvalue()


class UpdateTests(unittest.TestCase):
    def test_only_newer_versions(self):
        import json
        for version, available in [("1.4.0", False), ("1.3.9", False), ("1.10.0", True)]:
            data = dict(version=version, file=f"Notchi-{version}-Windows-x64.zip", sha256="a" * 64, bytes=123)
            with patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(data).encode())):
                self.assertEqual(bool(updater.check_release()), available)

    def test_download_verifies_and_extracts_only_executable(self):
        payload = package()
        release = dict(file="Notchi-1.5.0-Windows-x64.zip", bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "stage"
            stage.mkdir()
            with patch.object(updater.tempfile, "mkdtemp", return_value=str(stage)), patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(payload)):
                self.assertEqual(updater.download_release(release), stage)
            self.assertEqual((stage / "Notchi.exe").read_bytes(), b"MZ synthetic test executable")
            self.assertFalse((Path(temporary) / "outside.txt").exists())

    def test_corruption_and_oversized_download_are_rejected_and_cleaned(self):
        payload = package()
        for size in (len(payload), len(payload) - 1):
            with tempfile.TemporaryDirectory() as temporary:
                stage = Path(temporary) / "stage"
                stage.mkdir()
                with patch.object(updater.tempfile, "mkdtemp", return_value=str(stage)), patch.object(updater.urllib.request, "urlopen", return_value=io.BytesIO(payload)):
                    with self.assertRaises(ValueError):
                        updater.download_release(dict(file="test.zip", bytes=size, sha256="0" * 64))
                self.assertFalse(stage.exists())

    def test_windows_helper_replaces_executable_in_path_with_apostrophe(self):
        with tempfile.TemporaryDirectory(prefix="Notchi's test ") as temporary:
            stage = Path(temporary)
            target = stage / "installed.exe"
            target.write_bytes(b"old")
            (stage / "Notchi.exe").write_bytes(b"new")
            with patch.object(updater.subprocess, "Popen"):
                updater.launch_installer(stage, target, 2147483647)
            script = stage / "install.ps1"
            # Exercise the real replacement code without launching a test executable,
            # displaying UI, or modifying the user's update log.
            code = script.read_text(encoding="utf-8-sig")
            code = code.replace("Start-Process -FilePath $target -WorkingDirectory ([System.IO.Path]::GetDirectoryName($target))", "# test: restart suppressed")
            code = code.replace("Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue", "# test: log untouched")
            script.write_text(code, encoding="utf-8-sig")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)], capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), b"new")
            self.assertFalse(Path(str(target) + ".update-backup").exists())


if __name__ == "__main__":
    unittest.main()
