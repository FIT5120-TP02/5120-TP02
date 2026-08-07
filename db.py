# Database connection. The one file that knows where the database is.
#
#     import db
#     conn = db.connect()
#
# Everything defaults to the team's shared instance, so a teammate only has to
# supply the password. Point somewhere else by setting the environment:
#
#     PowerShell:  $env:DB_HOST="127.0.0.1"; $env:DB_PORT="3307"; $env:DB_USER="root"
#     bash:        export DB_HOST=127.0.0.1 DB_PORT=3307 DB_USER=root

import os
import sys

import pymysql

SHARED_HOST = "tp02fit5120.c1qymwwke45u.ap-southeast-2.rds.amazonaws.com"
SHARED_PORT = 3306
SHARED_USER = "admin"
SHARED_NAME = "onboarding"


def host():
    return os.environ.get("DB_HOST", SHARED_HOST)


def is_local():
    """True when we are pointed at a sandbox rather than the shared database.

    Anything destructive checks this first. Wiping your own container costs two
    minutes; wiping the shared one stops five other people.
    """
    return host() in ("127.0.0.1", "localhost", "::1")


def connect():
    """Open a connection. The caller closes it."""
    password = os.environ.get("DB_PASSWORD")
    if not password:
        sys.exit(
            "DB_PASSWORD is not set.\n"
            "  PowerShell:  $env:DB_PASSWORD = Read-Host 'Password'\n"
            "  bash:        read -rs DB_PASSWORD && export DB_PASSWORD\n"
            "Ask the team for it - it is deliberately not in the repository."
        )

    return pymysql.connect(
        host=host(),
        port=int(os.environ.get("DB_PORT", SHARED_PORT)),
        user=os.environ.get("DB_USER", SHARED_USER),
        password=password,
        database=os.environ.get("DB_NAME", SHARED_NAME),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
