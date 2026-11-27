"""Exercise update states in an isolated Tk session, with no network or account access."""
import os
import tempfile
import time
import unittest
from unittest.mock import patch
import notch_widget as app


class UpdateUITests(unittest.TestCase):
    def test_settings_check_retry_available_and_source_guard(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, LOCALAPPDATA=temporary):
            root = app.tk.Tk()
            root.withdraw()
            errors = []
            root.report_callback_exception = lambda *error: errors.append(error)
            try:
                widget = app.NotchDesktopWidget(root)
                widget.open_settings()
                def settle():
                    deadline = time.monotonic() + 3
                    while widget.update_busy and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertFalse(widget.update_busy)
                with patch.object(app, "check_release", return_value=None):
                    widget.update_button.invoke()
                    self.assertEqual(widget.update_button.cget("state"), "disabled")
                    settle()
                    self.assertIn("up to date", widget.update_note.get())
                with patch.object(app, "check_release", side_effect=OSError("Offline")):
                    widget.handle_update()
                    settle()
                    self.assertIn("Offline", widget.update_note.get())
                with patch.object(app, "check_release", return_value={"version": "1.6.0"}):
                    widget.handle_update()
                    widget.settings_win.destroy()
                    settle()
                    widget.open_settings()
                    self.assertEqual(widget.update_button.cget("text"), "Update and restart")
                widget.handle_update()
                self.assertIn("packaged Notchi.exe", widget.update_note.get())
                with patch.object(app.sys, "frozen", True, create=True), patch.object(app, "download_release", return_value=temporary), patch.object(app, "launch_installer") as installer, patch.object(widget, "close_app") as close:
                    widget.handle_update()
                    settle()
                    installer.assert_called_once_with(temporary, app.sys.executable, os.getpid())
                    close.assert_called_once()
                self.assertFalse(errors, errors)
            finally:
                for job in root.tk.call("after", "info"):
                    root.after_cancel(job)
                root.destroy()


if __name__ == "__main__":
    unittest.main()
