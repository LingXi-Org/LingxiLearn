"""Serve the exported frontend with the same deep-link fallback as FastAPI."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class StaticFallbackHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        pathname = self.path.split("?", 1)[0]
        requested = Path(self.translate_path(pathname))
        if not requested.exists() and not requested.is_file():
            if pathname.startswith("/workspace/"):
                self.path = "/workspace/lingxi/home/index.html"
            else:
                self.path = "/index.html"
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    handler = lambda *handler_args, **kwargs: StaticFallbackHandler(  # noqa: E731
        *handler_args, directory=str(args.directory), **kwargs
    )
    ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
