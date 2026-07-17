import sys

from dotenv import load_dotenv

from core.extraction_runner import run_extraction


def main():
    load_dotenv()
    if len(sys.argv) > 1 and sys.argv[1] == "extract":
        run_extraction()
    else:
        print("Usage: python main.py extract")


if __name__ == "__main__":
    main()
