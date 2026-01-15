from pathlib import Path
from datetime import datetime
import pandas as pd

from src.processing.dataframe import clean_df
from src.io.readers import load_csv_chunks, read_pdf_chunks
from src.io.writers import save_csv, save_csv_safe, save_excel, save_txt, save_pdf
from src.io.opener import open_file


class IntelligentDataCleaner:
    """
    Main orchestrator for intelligent data cleaning.

    This class handles:
    - Iterating over raw data files (CSV, TXT, PDF)
    - Cleaning and deduplicating data
    - Saving results in multiple formats (CSV, Excel, TXT, PDF)
    - Automatically opening processed files

    Attributes:
        base_dir (Path): Base directory of the project.
        raw_dir (Path): Directory containing raw input files.
        output_dir (Path): Directory where cleaned outputs are saved.
    """

    def __init__(self, base_dir: Path) -> None:
        """
        Initialize the data cleaner.

        Creates input and output directories if they do not exist.
        """
        self.base_dir: Path = base_dir
        self.raw_dir: Path = base_dir / "raw_data"
        self.output_dir: Path = base_dir / "output"

        # Ensure directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_file(self, file: Path) -> None:
        """
        Process a single data file.

        Steps:
        1. Load the file in chunks
        2. Clean and normalize the data
        3. Remove duplicates
        4. Save the cleaned data in multiple formats
        5. Open all output files automatically

        Args:
            file (Path): Path to the input file.
        """
        if file.suffix.lower() in {".csv", ".txt"}:
            # Load CSV or TXT in chunks and clean
            chunks = [clean_df(chunk) for chunk in load_csv_chunks(file)]
            df = pd.concat(chunks, ignore_index=True)

        elif file.suffix.lower() == ".pdf":
            # Load PDF pages and clean
            chunks = [clean_df(page_df) for page_df in read_pdf_chunks(file)]
            df = pd.concat(chunks, ignore_index=True)

        else:
            # Skip unsupported file types
            return

        # Generate timestamped base name for output files
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name: str = f"CLEANED_{file.stem}_{timestamp}"
        output_path: Path = self.output_dir / base_name

        # Save in multiple formats
        save_csv(df, output_path.with_suffix(".csv"))
        save_csv_safe(df, output_path.with_name(base_name + "_SAFE.csv"))
        save_excel(df, output_path.with_suffix(".xlsx"))
        save_txt(df, output_path.with_suffix(".txt"))
        save_pdf(df, output_path.with_suffix(".pdf"))

        # Automatically open all generated files
        for path in self.output_dir.glob(f"{base_name}*"):
            open_file(path)
