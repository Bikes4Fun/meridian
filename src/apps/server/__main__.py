"""Run server: python -m apps.server [serve] [port]."""

import os
import sys

# Ensure src is on path for Railway/deploy (shared is at src/shared)
_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
if _src not in sys.path:
    sys.path.insert(0, _src)


def main():
    try:
        from ...shared.config import (
            get_server_host,
            get_server_port,
            find_available_port,
        )
    except ImportError:
        from shared.config import (
            get_server_host,
            get_server_port,
            find_available_port,
        )

    host = get_server_host()
    start_port = get_server_port()

    args = sys.argv[1:]
    if args and args[0] == "serve":
        args = args[1:]
    elif args and not args[0].isdigit():
        print(
            f"Unknown command '{args[0]}'. Supported: serve [port], or [port] for backward compatibility."
        )
        sys.exit(2)

    if args:
        try:
            start_port = int(args[0])
        except ValueError:
            pass
    port = find_available_port(host, start_port)
    if port != start_port:
        print(f"Port {start_port} in use, using port {port} instead.")
    os.environ["PORT"] = str(port)

    from .api import run_server

    run_server()


if __name__ == "__main__":
    main()
