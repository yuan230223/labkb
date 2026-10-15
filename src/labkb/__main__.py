import argparse

import uvicorn
from dotenv import load_dotenv

from labkb.config import Settings


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="研知 LabKB 本地知识库")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    config = Settings.from_env()
    config.check_bind(args.host)
    from labkb.app import create_app

    uvicorn.run(create_app(config), host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
