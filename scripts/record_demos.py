#!/usr/bin/env python3
"""Record the existing offline HTML scenarios as finite, shareable GIFs."""

import hashlib
import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demos"
WIDTH, HEIGHT = 1120, 1000
SOURCES = ("index.html", "style.css", "demo.js")

# Keep the actual demo view and labels; omit surrounding landing-page prose.
RECORDING_CSS = """
.intro, .invitation, footer { display: none !important; }
.masthead { min-height: 80px !important; }
.section-heading { padding: 18px 0 !important; }
.workbench { height: 640px !important; }
.story { padding: 24px !important; }
.inspector { padding: 24px !important; }
.inspector pre { font-size: 13px !important; line-height: 1.65 !important; }
.controls { padding: 14px 0 !important; }
html { overflow: hidden !important; }
"""


class DemoRecorder:
    """Drive local page controls in an ephemeral WebKit context, never a profile."""

    def __init__(self):
        # Rendering dependencies are maintainer-only, not visitor or CI requirements.
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gdk, GLib, Gtk, WebKit2

        self.Gdk, self.GLib, self.Gtk, self.WebKit = Gdk, GLib, Gtk, WebKit2
        self.context = WebKit2.WebContext.new_ephemeral()
        # Local file assets need no network. Do not inherit system proxy/account state.
        self.context.get_website_data_manager().set_network_proxy_settings(
            WebKit2.NetworkProxyMode.CUSTOM,
            WebKit2.NetworkProxySettings.new("http://127.0.0.1:9", []),
        )
        self.view = WebKit2.WebView.new_with_context(self.context)
        self.view.get_settings().set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.NEVER)
        style = WebKit2.UserStyleSheet.new(
            RECORDING_CSS, WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserStyleLevel.USER, None, None,
        )
        self.view.get_user_content_manager().add_style_sheet(style)
        self.window = Gtk.Window()
        self.window.set_default_size(WIDTH, HEIGHT)
        self.window.add(self.view)
        self.window.show_all()

    def wait(self, start):
        """Bound each async render operation and propagate callback errors."""
        loop, result, errors = self.GLib.MainLoop(), [], []

        def done(value=None, error=None):
            if error is None:
                result.append(value)
            else:
                errors.append(error)
            loop.quit()

        def expired():
            done(error=TimeoutError("Offline demo rendering timed out"))
            return False

        timer = self.GLib.timeout_add_seconds(20, expired)
        try:
            start(done)
            if not result and not errors:
                loop.run()
            if errors:
                raise errors[0]
            return result[0]
        finally:
            if self.GLib.MainContext.default().find_source_by_id(timer):
                self.GLib.source_remove(timer)

    def load(self):
        handlers = []

        def start(done):
            def changed(view, event):
                if event == self.WebKit.LoadEvent.FINISHED:
                    done()

            def failed(view, event, uri, error):
                done(error=RuntimeError("Could not load the offline demo"))
                return True

            handlers.append(self.view.connect("load-changed", changed))
            handlers.append(self.view.connect("load-failed", failed))
            self.view.load_uri((DEMO / "index.html").as_uri())

        try:
            self.wait(start)
        finally:
            for handler in handlers:
                self.view.disconnect(handler)

    def javascript(self, script):
        def start(done):
            def evaluated(view, result, data):
                try:
                    done(view.evaluate_javascript_finish(result).to_json(0))
                except self.GLib.Error as error:
                    done(error=error)

            self.view.evaluate_javascript(script, -1, None, None, None, evaluated, None)

        return json.loads(self.wait(start))

    def screenshot(self):
        from PIL import Image

        def start(done):
            def capture():
                try:
                    pixels = self.Gdk.pixbuf_get_from_window(self.view.get_window(), 0, 0, WIDTH, HEIGHT)
                    if pixels is None:
                        raise RuntimeError("The offline recording window is not drawable")
                    success, data = pixels.save_to_bufferv("png", [], [])
                    if not success:
                        raise RuntimeError("Could not encode the offline frame")
                    done(Image.open(io.BytesIO(data)).convert("RGB"))
                except (self.GLib.Error, OSError, RuntimeError) as error:
                    done(error=error)
                return False

            # Allow the compositor to paint the DOM changes before taking a frame.
            self.GLib.timeout_add(250, capture)

        frame = self.wait(start)
        if frame.size != (WIDTH, HEIGHT):
            raise ValueError("Unexpected capture dimensions")
        return frame

    def record(self, directory):
        manifest = {
            "schema_version": 1, "synthetic": True, "provider_calls": 0,
            "renderer": "WebKitGTK", "width": WIDTH, "height": HEIGHT,
            "sources": {name: digest(DEMO / name) for name in SOURCES},
            "recorder_sha256": digest(Path(__file__)),
            "recordings": [],
        }
        scenarios = self.javascript("Object.keys(WgptDemo.scenarios)")
        for scenario in scenarios:
            if scenario not in {"protocol", "recovery", "tools"}:
                raise ValueError("Review new scenarios before publishing recordings")
            self.javascript(f"document.querySelector('[data-scenario={scenario}]').click(); true")
            count = self.javascript(f"WgptDemo.scenarios.{scenario}.steps.length")
            frames, states, durations = [], [], []
            for index in range(count + 1):
                if index:
                    self.javascript("document.getElementById('next').click(); true")
                state = self.javascript("""(() => {
                    const controls = document.querySelector('.controls').getBoundingClientRect();
                    const inspector = document.getElementById('event-output');
                    const panels = [...document.querySelectorAll('.story, .inspector')];
                    return {
                        state: document.getElementById('state').textContent,
                        submissions: Number(document.getElementById('submissions').textContent),
                        current: document.querySelectorAll('[aria-current=step]').length,
                        completed: document.getElementById('next').disabled,
                        bottom: controls.bottom, viewport: innerHeight,
                        fits: controls.bottom <= innerHeight && inspector.scrollHeight <= inspector.clientHeight
                            && panels.every(panel => panel.scrollHeight <= panel.clientHeight),
                        synthetic: document.querySelector('.offline').textContent.includes('SYNTHETIC')
                    };
                })()""")
                if not state["fits"] or not state["synthetic"]:
                    raise ValueError(f"Capture would hide content or its synthetic label: {state}")
                expected = "idle" if not index else self.javascript(f"WgptDemo.scenarios.{scenario}.steps[{index - 1}].state")
                if state["state"] != expected or state["completed"] != (index == count):
                    raise ValueError("The recording is out of sync with the demo controls")
                frames.append(self.screenshot())
                states.append({"state": state["state"], "submissions": state["submissions"]})
                durations.append(2000 if not index else 6500 if state["state"] == "streaming" else 3500)
            output = directory / f"{scenario}.gif"
            # No loop extension: play once, then leave the completed state visible.
            frames[0].save(
                output, save_all=True, append_images=frames[1:], format="GIF",
                duration=durations, optimize=True, disposal=1,
            )
            manifest["recordings"].append({
                "file": output.name, "sha256": digest(output), "frames": len(frames),
                "duration_ms": sum(durations), "states": states,
            })
            print(f"Recorded {scenario}: {len(frames)} frames, {output.stat().st_size} bytes")
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def close(self):
        self.window.destroy()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    os.environ.update(GDK_BACKEND="x11", LIBGL_ALWAYS_SOFTWARE="1", WEBKIT_DISABLE_DMABUF_RENDERER="1", GDK_SCALE="1", GDK_DPI_SCALE="1")
    destination = DEMO / "recordings"
    destination.mkdir(exist_ok=True)
    recorder = DemoRecorder()
    try:
        recorder.load()
        recorder.record(destination)
    finally:
        recorder.close()


if __name__ == "__main__":
    main()
