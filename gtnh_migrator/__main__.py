import argparse
from .app import serve


def main():
    parser = argparse.ArgumentParser(description='Open the local GTNH RWG2 migration wizard')
    parser.add_argument('--port', type=int, default=0, help='Local port; default: choose an available port')
    parser.add_argument('--no-browser', action='store_true', help='Print the address without opening a browser')
    args = parser.parse_args()
    serve(args.port, not args.no_browser)


if __name__ == '__main__':
    main()
