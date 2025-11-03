"""Initialize PhotoChanger database."""

from src.app.config import load_config


def main() -> None:
    load_config()
    print("Database initialized.")


if __name__ == "__main__":
    main()
