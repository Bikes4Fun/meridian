"""Run server: python -m apps.server [port]"""

import os
import sys


def main():
    from ...shared.config import (
        get_server_host,
        get_server_port,
        find_available_port,
    )

    host = get_server_host()
    start_port = get_server_port()
    if len(sys.argv) > 1:
        try:
            start_port = int(sys.argv[1])
        except ValueError:
            pass
    port = find_available_port(host, start_port)
    if port != start_port:
        print("Port %s in use, using port %s instead." % (start_port, port))
    os.environ["PORT"] = str(port)

    from .api import run_server

    run_server()


if __name__ == "__main__":
    main()
