"""Keep query strings out of the application's standard HTTP access logs."""

import logging


class QueryStringFilter(logging.Filter):
    # Uvicorn access records pass client, method, request target, version and status.
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            if isinstance(args[2], str):
                args[2] = args[2].split("?", 1)[0]
                record.args = tuple(args)
        return True
