"""Load the skill's bundled rule pack."""

import base64
import gzip
import json

ARCHIVE = "H4sIAAAAAAACE6tWKk7OSM1NVLJSKi1O0y8zVNJRKkotLM0sSk1RsopWykvMTQUKlaUWFWfm5ynF1gIA9dqtGTEAAAA="

policy = json.loads(gzip.decompress(base64.b64decode(ARCHIVE)))
REQUIRED_FIELDS = tuple(policy["required"])
