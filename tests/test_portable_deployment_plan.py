"""Cross-VPS simulation and non-authorizing deployment boundary tests."""
import copy
import unittest

from agency.portable_deployment_plan import plan
from tests.test_deployment_manifest import BASE


def host(profile):
    manifest = copy.deepcopy(BASE)
    manifest["paths"] = {
        key: "/srv/" + profile + "/" + key for key in manifest["paths"]
    }
    manifest["units"] = {
        key: profile + "-" + key.replace("_", "-") + ".service"
        for key in manifest["units"]
    }
    manifest["identities"] = {
        "trusted_user": profile + "_trusted",
        "worker_user": profile + "_worker",
        "trusted_group": profile + "_agents",
    }
    return manifest


def resolver_with_ids(uid, gid, executable):
    def resolve(manifest):
        return {
            "identity_resolved": True,
            "runtime_behavior_attested": False,
            "sandbox_authorized": False,
            "cutover_authorized": False,
            "paths": dict(manifest["paths"]),
            "units": dict(manifest["units"]),
            "uids": {"trusted_user": uid, "worker_user": uid + 1},
            "gids": {"trusted_group": gid},
            "systemctl": executable,
        }
    return resolve


class PortableDeploymentPlanTests(unittest.TestCase):
    def test_multiple_host_profiles_never_authorize(self):
        profiles = (
            ("ubuntu", 997, 987, "/usr/bin/systemctl"),
            ("debian", 1101, 1102, "/bin/systemctl"),
            ("armbian", 2001, 2002, "/usr/local/sbin/systemctl"),
        )
        for name, uid, gid, executable in profiles:
            with self.subTest(host=name):
                manifest = host(name)
                report = plan(manifest, resolver=resolver_with_ids(uid, gid, executable))
                self.assertEqual(report["uids"]["trusted_user"], uid)
                self.assertEqual(report["systemctl"], executable)
                self.assertFalse(report["installation_performed"])
                self.assertFalse(report["broker_execution_authorized"])
                self.assertFalse(report["admission_authorized"])
                self.assertFalse(report["cutover_authorized"])
                self.assertEqual(report["production_readiness"], "NO_GO")

    def test_manifest_injection_rejected(self):
        manifest = host("ubuntu")
        for key, value in (
            ("execute", True),
            ("cutover_authorized", True),
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(manifest)
                changed[key] = value
                with self.assertRaises(ValueError):
                    plan(changed, resolver=resolver_with_ids(1001, 1002, "/usr/bin/systemctl"))

    def test_invalid_unit_and_path_rejected(self):
        manifest = host("debian")
        manifest["units"]["candidate_broker"] = "broker;restart.service"
        with self.assertRaises(ValueError):
            plan(manifest, resolver=resolver_with_ids(1001, 1002, "/usr/bin/systemctl"))
        manifest = host("debian")
        manifest["paths"]["admission_lock"] = "/srv/../unsafe"
        with self.assertRaises(ValueError):
            plan(manifest, resolver=resolver_with_ids(1001, 1002, "/usr/bin/systemctl"))

    def test_resolver_cannot_promote_cutover_or_sandbox(self):
        for field in ("cutover_authorized", "sandbox_authorized",
                      "runtime_behavior_attested"):
            with self.subTest(field=field):
                resolver = resolver_with_ids(1001, 1002, "/usr/bin/systemctl")
                def unsafe(manifest):
                    result = resolver(manifest)
                    result[field] = True
                    return result
                with self.assertRaises(PermissionError):
                    plan(host("ubuntu"), resolver=unsafe)

    def test_resolver_cannot_replace_lock_or_units(self):
        for field, key, value in (
            ("paths", "admission_lock", "/tmp/untrusted.lock"),
            ("units", "candidate_recovery", "attacker.service"),
        ):
            with self.subTest(field=field):
                resolver = resolver_with_ids(1001, 1002, "/usr/bin/systemctl")
                def unsafe(manifest):
                    result = resolver(manifest)
                    result[field][key] = value
                    return result
                with self.assertRaises(PermissionError):
                    plan(host("ubuntu"), resolver=unsafe)

    def test_root_and_unresolved_identity_denied(self):
        for uid, gid in ((0, 1000), (1000, 0), (-1, 1000)):
            with self.subTest(uid=uid, gid=gid):
                with self.assertRaises(PermissionError):
                    plan(host("ubuntu"), resolver=resolver_with_ids(uid, gid, "/usr/bin/systemctl"))


if __name__ == "__main__":
    unittest.main()
