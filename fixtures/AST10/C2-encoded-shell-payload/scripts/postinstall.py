"""Environment bootstrap run once when the skill is imported."""

import base64
import json

DEFAULTS = "eyJ0aW1lb3V0X3NlY29uZHMiOjMwLCJsb2NhbGUiOiJlbi1HQiIsImZvcm1hdCI6Im1hcmtkb3duIn0="

settings = json.loads(base64.b64decode(DEFAULTS))
print("invoice-helper defaults:", settings["format"])
