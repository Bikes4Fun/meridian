"""Run server: python -m apps.server [port]. Seed DB: python -m apps.server seed."""

import os
import sys


def main():
    from ...shared.config import (
        get_server_host,
        get_server_port,
        get_database_path,
        find_available_port,
    )

    if len(sys.argv) > 1 and sys.argv[1].lower() == "seed":
        from ...shared.config import DatabaseConfig
        from ...dev.demo.seed import demo_main
        from .database import DatabaseManager

        db_path = get_database_path()
        db_config = DatabaseConfig(path=db_path, create_if_missing=True)
        db = DatabaseManager(db_config)
        result = db.create_database_schema()
        if not result.success:
            print("Schema creation failed:", result.error)
            sys.exit(1)
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

    from .api import run_server

    run_server()


if __name__ == "__main__":
    main()
