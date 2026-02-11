import sys


def main():
    from .cli import app

    try:
        app()
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
