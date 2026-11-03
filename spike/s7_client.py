"""S7 - socket client: ping, invalid message, permissions and path-length check. Stdlib only."""
import json
import os
import pwd
import socket
import stat
import sys

SUN_PATH_MAX = 104  # macOS sockaddr_un.sun_path size, including the trailing NUL


def call(path: str, payload: bytes) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(path)
        s.sendall(payload)
        return s.recv(4096).decode("utf-8")


def main() -> None:
    path = sys.argv[1]
    st = os.stat(path)
    print("is socket:", stat.S_ISSOCK(st.st_mode), "mode:", oct(st.st_mode & 0o777),
          "owner is me:", st.st_uid == os.getuid())
    n = len(path.encode("utf-8"))
    home_len = len(os.path.expanduser("~").encode("utf-8"))
    user_len = len(pwd.getpwuid(os.getuid()).pw_name.encode("utf-8"))
    print(f"path length {n} bytes of max {SUN_PATH_MAX - 1}; spare for a longer user name: {SUN_PATH_MAX - 1 - n}"
          f" (home {home_len} bytes, user name {user_len} bytes)")
    print("ping ->", call(path, json.dumps({"jsonrpc": "2.0", "method": "ping", "id": 1}).encode()))
    print("invalid ->", call(path, b'{"jsonrpc":"2.0","method":"delete","id":2}'))
    print("garbage ->", call(path, b"\xff\xfe not json"))


if __name__ == "__main__":
    main()
