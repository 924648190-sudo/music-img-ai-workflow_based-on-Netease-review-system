"""Call the published Dify Workflow; API credentials come from the environment."""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def load_env(path):
    """Read simple KEY=value lines without executing shell code or overriding env."""
    if not path.is_file():
        return
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key.isidentifier():
            raise ValueError(f"Invalid .env syntax at line {number}")
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed .env value at line {number}")
            value = value[1:-1]
        os.environ.setdefault(key, value)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward an Authorization header to a redirected endpoint.
        return None


def make_request(query, song_url=""):
    key = os.environ.get("DIFY_API_KEY", "").strip()
    if not key:
        raise ValueError("Set DIFY_API_KEY in your environment or local .env")
    base = os.environ.get("DIFY_API_BASE_URL", "https://api.dify.ai/v1").rstrip("/")
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("DIFY_API_BASE_URL must be an HTTPS URL without credentials, query or fragment")
    payload = {
        "inputs": {"userinput_query": query, "song_url": song_url},
        "response_mode": "blocking",
        # A fresh pseudonymous identifier; never use a personal email/account ID.
        "user": "cli-" + uuid.uuid4().hex,
    }
    return Request(
        base + "/workflows/run",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )


def extract_outputs(response):
    data = response.get("data", {})
    if data.get("status") not in ("succeeded", "partial-succeeded"):
        # Remote error bodies may contain user input; do not print them.
        raise ValueError("Workflow did not succeed; inspect the private Dify run log")
    outputs = data.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError("Workflow returned no outputs; inspect the private Dify run log")
    if data.get("status") == "partial-succeeded":
        print("Workflow partially succeeded; an optional step failed. Check Dify privately.", file=sys.stderr)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, required=True,
                        help="UTF-8 JSON with userinput_query and optional song_url")
    args = parser.parse_args()
    try:
        load_env(ROOT / ".env")
        inputs = json.loads(args.input_file.read_text(encoding="utf-8"))
        query, song_url = inputs.get("userinput_query"), inputs.get("song_url", "")
        if not isinstance(query, str) or not query.strip() or not isinstance(song_url, str):
            raise ValueError("Input requires a nonempty string userinput_query and a string song_url")
        timeout = float(os.environ.get("DIFY_API_TIMEOUT", "360"))
        if not 0 < timeout <= 3600:
            raise ValueError("DIFY_API_TIMEOUT must be between 0 and 3600 seconds")
        request = make_request(query, song_url)
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            outputs = extract_outputs(json.load(response))
        # Only end-node output, never raw headers, API keys or the full run object.
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as error:
        print(f"Dify request failed (HTTP {error.code}); response body withheld", file=sys.stderr)
    except (ValueError, OSError, URLError, TypeError, AttributeError):
        print("Request failed. Check input JSON, environment settings and private Dify run logs; sensitive details withheld.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
