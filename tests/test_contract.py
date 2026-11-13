import unittest

from vibedemo import contract

VALID = """# demo contract
app: hello-vibe
owner: team-web
cost_center:
env: dev
archi: stateless
port: 8080        # nginx-unprivileged
size: S
protection: none
tracing: true
expires: "2027-01-31"
"""


class ParseTest(unittest.TestCase):
    def test_parse_types_and_comments(self):
        data = contract.parse(VALID)
        self.assertEqual(data["app"], "hello-vibe")
        self.assertEqual(data["port"], 8080)
        self.assertIs(data["tracing"], True)
        self.assertIsNone(data["cost_center"])
        self.assertEqual(data["expires"], "2027-01-31")

    def test_nested_yaml_is_refused(self):
        with self.assertRaises(contract.ContractSyntaxError):
            contract.parse("app: x\nsize:\n  cpu: 1\n")

    def test_duplicate_is_refused(self):
        with self.assertRaises(contract.ContractSyntaxError):
            contract.parse("app: a\napp: b\n")

    def test_hash_inside_quotes_kept(self):
        self.assertEqual(contract.parse('owner: "a#b"\n')["owner"], "a#b")


class ValidateTest(unittest.TestCase):
    def check(self, text):
        return contract.validate(contract.parse(text))

    def test_valid_dev_contract(self):
        out, errors = self.check(VALID)
        self.assertEqual(errors, [])
        self.assertEqual(out["replicas"], 1)   # dev default
        self.assertEqual(out["size"], "S")

    def test_prod_rules(self):
        text = VALID.replace("env: dev", "env: prod").replace("replicas", "x")
        out, errors = self.check(text)
        joined = " ".join(errors)
        self.assertIn("cost_center is mandatory in prod", joined)
        self.assertIn("expires is forbidden in prod", joined)
        self.assertEqual(out["replicas"], 2)    # prod default

    def test_prod_min_replicas(self):
        text = VALID.replace("env: dev", "env: prod").replace("cost_center:", "cost_center: cc-42") \
            .replace('expires: "2027-01-31"', "replicas: 1")
        _, errors = self.check(text)
        self.assertEqual(errors, ["prod requires at least 2 replicas"])

    def test_backend_db_not_supported(self):
        _, errors = self.check(VALID.replace("archi: stateless", "archi: backend-db"))
        self.assertTrue(any("not supported by the platform yet" in e for e in errors))

    def test_bad_app_name_and_owner(self):
        _, errors = self.check(VALID.replace("hello-vibe", "Hello_Vibe").replace("team-web", "me@corp.com"))
        self.assertTrue(any(e.startswith("app ") for e in errors))
        self.assertTrue(any(e.startswith("owner ") for e in errors))

    def test_unknown_and_missing_fields(self):
        _, errors = self.check("app: x\nfoo: bar\n")
        self.assertTrue(any("unknown field 'foo'" in e for e in errors))
        self.assertTrue(any("'port' is required" in e for e in errors))

    def test_bad_values(self):
        text = VALID.replace("port: 8080", "port: 99999").replace("size: S", "size: XL") \
            .replace("protection: none", "protection: weekly").replace('"2027-01-31"', "31/01/2027")
        _, errors = self.check(text)
        self.assertEqual(len(errors), 4, errors)

    def test_describe(self):
        out, _ = self.check(VALID)
        text = "\n".join(contract.describe(out))
        self.assertIn("Development", text)
        self.assertIn("requests 100m CPU", text)


if __name__ == "__main__":
    unittest.main()
