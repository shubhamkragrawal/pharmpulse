from dotenv import load_dotenv

load_dotenv()

from core.extraction_runner import build_dsn
from domains.pharma.extractors import CTGovExtractor

if __name__ == "__main__":
    extractor = CTGovExtractor(db_dsn=build_dsn(), page_size=1000)
    total = extractor.run()
    print(f"done. total upserted this run: {total}")
