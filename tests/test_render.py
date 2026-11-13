import json
import tempfile
import unittest
from pathlib import Path

from vibedemo import contract, render

C = contract.validate(contract.parse(
    "app: hello-vibe\nowner: team-web\nenv: preprod\narchi: stateless\nport: 8080\n"
    "size: M\nprotection: daily\ntracing: false\n"))[0]
SHA = "0123456789abcdef0123456789abcdef01234567"


class RenderTest(unittest.TestCase):
    def test_deployment_content(self):
        files = render.render_all(C, "ghcr.io/me/vibe-demo-app:" + SHA, SHA, "vibe-demo")
        app = files["app.yaml"]
        self.assertIn('namespace: "vibe-demo"', app)
        self.assertIn("replicas: 2", app)                       # preprod default
        self.assertIn('cpu: "250m"', app)                       # size M request
        self.assertIn('memory: "512Mi"', app)                   # size M limit
        self.assertIn('vibedemo.nutanix.com/sha: "%s"' % SHA, app)
        self.assertIn("type: LoadBalancer", app)
        self.assertIn("containerPort: 8080", app)
        self.assertNotIn("cost-center", app)                    # not set -> no label
        self.assertIn("resources:\n  - app.yaml", files["kustomization.yaml"])

    def test_deterministic(self):
        a = render.render_all(C, "img:1", SHA, "ns")
        b = render.render_all(C, "img:1", SHA, "ns")
        self.assertEqual(a, b)

    def test_quoted_values_are_json_strings(self):
        app = render.render_all(C, "img:1", SHA, "ns")["app.yaml"]
        for line in app.splitlines():
            if line.strip().startswith("image:"):
                json.loads(line.split(":", 1)[1].strip())

    def test_write_replaces_old_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "old.yaml").write_text("x")
            Path(tmp, "README.md").write_text("keep")
            render.write_deploy_dir(tmp, render.render_all(C, "img:1", SHA, "ns"))
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["README.md", "app.yaml", "kustomization.yaml"])


if __name__ == "__main__":
    unittest.main()
