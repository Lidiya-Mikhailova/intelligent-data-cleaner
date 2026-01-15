from pathlib import Path
from src.core.cleaner import IntelligentDataCleaner
from src.core.logging_config import setup_logging



def main() -> None:
    """
    Entry point for the Intelligent Data Cleaner CLI.

    Responsibilities:
    1. Initialize the cleaner with the current project directory.
    2. Iterate over all files in the raw data folder.
    3. Process each file through the cleaning pipeline:
       - Load CSV, TXT, or PDF files.
       - Clean and normalize data.
       - Deduplicate rows.
       - Save results in multiple formats (CSV, Excel, TXT, PDF)
       - Open output files automatically.
    """
    project_dir: Path = Path.cwd()
    setup_logging(project_dir)

    cleaner = IntelligentDataCleaner(base_dir=project_dir)

    # Process all files in raw_data folder
    for file in cleaner.raw_dir.glob("*.*"):
        cleaner.process_file(file)


if __name__ == "__main__":
    main()
