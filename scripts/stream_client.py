"""Call /chat/stream and print the reply as it arrives, like a chat UI would."""

import json
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/chat/stream"
DEFAULT_MESSAGE = "Explain what a Forward Deployed Engineer does in 3 short paragraphs."


def main() -> None:
    message = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MESSAGE
    body = json.dumps({"message": message}).encode("utf-8")
    request = urllib.request.Request(
        URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue

                event = json.loads(line[len("data: "):])
                if "delta" in event:
                    print(event["delta"], end="", flush=True)
                elif "error" in event:
                    print(f"\n[error] {event['error']}")
                elif event.get("done"):
                    print(
                        f"\n\n[done] first token: {event['time_to_first_token_ms']} ms"
                        f" | total: {event['total_ms']} ms"
                        f" | chunks: {event['chunks']}"
                    )
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8")
        print(f"HTTP {error.code} {error.reason}")
        print(details)


if __name__ == "__main__":
    main()