r"""Tests for pipeline_state image-stage heuristic — must recognise uploaded
images by any absolute http(s) URL, not only URLs containing the literal "cdn".

Bug: _scan_article counted cdn_images with `r"!\[[^\]]*\]\(https?://[^)]*cdn"`,
requiring the substring "cdn" in the URL. S3 uploads use the configured
public_url_prefix (e.g. img.example.com) or the endpoint/bucket/key fallback
(s3.region.amazonaws.com/bucket/key) — neither needs "cdn". So in the
--upgrade no-state-file heuristic, a fully-imaged S3 article reported
cdn_images=0 and the images stage was wrongly judged not-done, needlessly
regenerating + re-uploading every image.

Fix: count any markdown image with an absolute http(s) URL. Local/relative
paths (pre-upload) still don't count, preserving the stage's intent.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "pipeline_state.py"
    spec = importlib.util.spec_from_file_location("pipeline_state", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ps = load_module()


def _scan(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        article = Path(tmp) / "article.md"
        article.write_text("---\nwriting_style: A\n---\n\n# T\n\n" + body, encoding="utf-8")
        return ps._scan_article(article)


class S3ImageHeuristicTests(unittest.TestCase):
    def test_s3_public_prefix_url_counts_as_processed(self):
        scan = _scan("![](https://img.example.com/articles/cover.jpg)\n")
        self.assertGreater(scan.cdn_images, 0)
        self.assertTrue(ps._stage_done_heuristic("images", scan))

    def test_s3_endpoint_bucket_key_url_counts(self):
        scan = _scan("![](https://s3.us-east-1.amazonaws.com/my-bucket/img/k.jpg)\n")
        self.assertGreater(scan.cdn_images, 0)
        self.assertTrue(ps._stage_done_heuristic("images", scan))

    def test_cdn_url_still_counts(self):
        scan = _scan("![](https://cdn.example.com/img.jpg)\n")
        self.assertGreater(scan.cdn_images, 0)

    def test_local_relative_image_does_not_count(self):
        # Pre-upload local path must NOT mark the images stage done.
        scan = _scan("![](images/cover.jpg)\n")
        self.assertEqual(scan.cdn_images, 0)
        self.assertFalse(ps._stage_done_heuristic("images", scan))


if __name__ == "__main__":
    unittest.main()
