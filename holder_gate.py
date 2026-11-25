"""One-shot handoff policy for the synthetic compositor probe.

Call only with presentation acknowledgements, not process readiness.
The compositor is responsible for rendering and executing fallback.
"""

class HolderGate:
    def __init__(self, timeout):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = timeout
        self.state = "desktop"
        self.deadline = None

    def begin(self, now):
        if self.state == "desktop":
            self.deadline = now + self.timeout
            self.state = "presenting-holder"
            return "present-wallpaper"

    def event(self, now, event):
        if self.state not in ("presenting-holder", "holding"):
            return None
        if now >= self.deadline or event == "failed":
            self.state = "fallback"
            return "restore-stock"
        if self.state == "presenting-holder" and event == "wallpaper-presented":
            self.state = "holding"
            return "stop-desktop-and-start-greeter"
        if self.state == "holding" and event == "greeter-presented":
            self.state = "done"
            return "release-holder"
