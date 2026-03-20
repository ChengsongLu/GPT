import argparse

import uvicorn

from mock.gitlab_server import FIXTURES_ROOT, create_mock_gitlab_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a reusable local mock GitLab server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=19001)
    parser.add_argument("--scenario", default="basic")
    parser.add_argument("--delay-ms", type=int, default=0)
    parser.add_argument("--fail-endpoint", choices=["project", "branches", "commits"], default=None)
    parser.add_argument("--fail-status", type=int, default=500)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = create_mock_gitlab_app(
        scenario=args.scenario,
        delay_ms=args.delay_ms,
        fail_endpoint=args.fail_endpoint,
        fail_status=args.fail_status,
    )
    available = ", ".join(sorted(path.name for path in FIXTURES_ROOT.iterdir() if path.is_dir()))
    print(f"Mock GitLab listening on http://{args.host}:{args.port} | scenario={args.scenario}")
    print(f"Available scenarios: {available}")
    uvicorn.run(app, host=args.host, port=args.port, reload=False)
