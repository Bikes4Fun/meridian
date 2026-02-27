"""Run server: python -m lib.server [port]. Seed DB: python -m lib.server seed."""
import os
import sys


def main():
    from ..config import get_server_host, get_server_port, get_database_path, find_available_port

    if len(sys.argv) > 1 and sys.argv[1].lower() == "seed":
        from ..demo.demo import demo_main
        db_path = get_database_path()
        ok = demo_main("0000000000", db_path=db_path)
        sys.exit(0 if ok else 1)

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

    from .app import run_server
    run_server()


if __name__ == "__main__":
    main()
