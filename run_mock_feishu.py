import argparse

import uvicorn

from mock.feishu_server import FIXTURES_ROOT, create_mock_feishu_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a reusable local mock Feishu server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=19002)
    parser.add_argument("--scenario", default="feishu_basic")
    parser.add_argument("--fail-endpoint", choices=["token", "records", "messages"], default=None)
    parser.add_argument("--fail-status", type=int, default=500)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = create_mock_feishu_app(
        scenario=args.scenario,
        fail_endpoint=args.fail_endpoint,
        fail_status=args.fail_status,
    )
    available = ", ".join(
        sorted(path.name for path in FIXTURES_ROOT.iterdir() if path.is_dir() and path.name.startswith("feishu_"))
    )
    print(f"Mock Feishu listening on http://{args.host}:{args.port} | scenario={args.scenario}")
    print(f"Available scenarios: {available}")
    uvicorn.run(app, host=args.host, port=args.port, reload=False)
