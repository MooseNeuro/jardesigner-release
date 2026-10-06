import json
import sys

if __name__ == "__main__":
    # Importing this pulls in moose, numpy, matplotlib, jsonschema etc.,
    # which is most of a worker's start-up time.
    from jardesigner.jardesigner import main

    if sys.argv[1:] == ["--wait"]:
        # Started ahead of time by the server: wait here, already imported,
        # until the run's arguments arrive as one JSON line on stdin.
        line = sys.stdin.readline()
        if not line:
            sys.exit(0)  # the server exited without using this worker
        sys.argv[1:] = json.loads(line)
    sys.exit(main())
