"""Isolated in-memory cutover adapter; never touches production services."""
import contextlib


class SimulatedAdapter:
    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []
        self.frozen = False
        self.legacy = True
        self.new = False
        self.route = "legacy"
        self.consumed = set()
        self.quarantined = False

    def _step(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise RuntimeError("Injected failure: " + name)

    @contextlib.contextmanager
    def admission_drain(self):
        self._step("admission_drain")
        yield

    def attest(self):
        self._step("attest")

    def freeze(self):
        self.frozen = True
        self._step("freeze")

    def quiesce(self):
        self._step("quiesce")

    def stop_old(self):
        self.legacy = False
        self._step("stop_old")

    def bootstrap(self):
        self._step("bootstrap")

    def start_new(self):
        self.new = True
        self._step("start_new")

    def route_new(self):
        self.route = "fenced"
        self._step("route_new")

    def replay_probe(self):
        self._step("replay_probe")
        token = "test-grant"
        if token in self.consumed:
            raise AssertionError("Unexpected existing grant")
        self.consumed.add(token)
        try:
            self._consume(token)
        except PermissionError:
            return
        raise AssertionError("Replay was accepted")

    def _consume(self, token):
        if token in self.consumed:
            raise PermissionError("Replay denied")
        self.consumed.add(token)

    def health(self):
        self._step("health")
        if self.route == "legacy" and not self.legacy:
            raise RuntimeError("Legacy broker unavailable")
        if self.route == "fenced" and not self.new:
            raise RuntimeError("Fenced broker unavailable")

    def rollback(self):
        self._step("rollback")
        self.route = "legacy"
        self.new = False
        self.legacy = True
        # Never clear consumed grant history.

    def unfreeze(self):
        self._step("unfreeze")
        self.frozen = False

    def quarantine(self):
        self.quarantined = True
        self.frozen = True
