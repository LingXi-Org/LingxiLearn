"""Optional standalone helper bundled as a readable Agent Skill resource."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?", default="朋友")
    parser.add_argument("place", nargs="?", default="这里")
    options = parser.parse_args()
    print(f"你好，{options.name}！欢迎来到{options.place}。")


if __name__ == "__main__":
    main()
