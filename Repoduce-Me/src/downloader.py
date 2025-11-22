import os
import shutil
import subprocess
import time
import stat
from typing import Optional

import urllib.request
from pathlib import Path

class Downloader:
    """
    A utility class to clone a GitHub repository into a local 'tmp' directory.

    It ensures the target 'tmp' directory is clean before every clone operation.
    Requires the 'git' command-line tool to be installed and accessible in the system's PATH.
    """
    
    def __init__(self, target_dir: str = "tmp", max_retries: int = 5, retry_delay: float = 1.0):

        self.target_dir = target_dir
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _cleanup_error_handler(self, func, path, exc_info):

        # The exception type is often PermissionError (a subclass of OSError) on WinError 5
        if issubclass(exc_info[0], PermissionError) or issubclass(exc_info[0], OSError):
            
            os.chmod(path, stat.S_IWUSR | stat.S_IWRITE)
            
            try:
                func(path)
                return  
            except Exception:

                pass 
        
        raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])
        
    def _cleanup(self) -> None:

        if not os.path.exists(self.target_dir):
            print(f"Target directory '{self.target_dir}' does not exist. Proceeding with clone.")
            return

        print(f"Cleaning up existing directory: '{self.target_dir}'...")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                shutil.rmtree(self.target_dir, onerror=self._cleanup_error_handler)
                print(f"Directory '{self.target_dir}' successfully deleted on attempt {attempt}.")
                return 
            except Exception as e:
                if attempt < self.max_retries:
                    print(f"Cleanup attempt {attempt} failed: {type(e).__name__} - {e}. Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"Error during directory cleanup after {self.max_retries} attempts: {e}")
                    raise 

    def download(self, github_link: str, branch: Optional[str] = None) -> bool:
        """
        Clones the specified GitHub repository into the target directory.
        """

        try:
            self._cleanup()
        except Exception:
            return False

        print(f"Attempting to clone '{github_link}' into '{self.target_dir}'...")

        command = ['git', 'clone']
        
        if branch:
            command.extend(['--branch', branch])
        
        command.extend([github_link, self.target_dir])

        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            print("Cloning successful.")
            print(f"Output:\n{result.stdout}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"\n--- ERROR DURING GIT CLONE ---")
            print(f"Command failed with exit code {e.returncode}: {' '.join(command)}")
            print(f"STDERR:\n{e.stderr}")
            print(f"------------------------------")
            return False
        except FileNotFoundError:
            print("\n--- ERROR: GIT NOT FOUND ---")
            print("The 'git' command was not found. Please ensure Git is installed and added to your system's PATH.")
            print("------------------------------")
            return False
        
    def download_pdf(self, pdf_url: str, output_path: Optional[str] = None) -> bool:
        """
        Download a PDF from the given URL and save it locally.

        If `output_path` is not provided, the file is saved under `self.target_dir`
        using the filename inferred from the URL (or 'downloaded.pdf' as fallback).
        """

        target_dir_path = Path(self.target_dir)
        target_dir_path.mkdir(parents=True, exist_ok=True)

        if output_path is None:
            filename = os.path.basename(pdf_url.split("?", 1)[0])  
            if not filename.lower().endswith(".pdf") or not filename:
                filename = "downloaded.pdf"

            output_path = str(target_dir_path / filename)

        print(f"Attempting to download PDF from '{pdf_url}' to '{output_path}'...")

        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(pdf_url) as response:
                    if response.status != 200:
                        raise OSError(f"HTTP status {response.status}")

                    with open(output_path, "wb") as f:
                        shutil.copyfileobj(response, f)

                print(f"PDF successfully downloaded on attempt {attempt}.")
                return True

            except Exception as e:
                if attempt < self.max_retries:
                    print(
                        f"Download attempt {attempt} failed: "
                        f"{type(e).__name__} - {e}. Retrying in {self.retry_delay}s..."
                    )
                    time.sleep(self.retry_delay)
                else:
                    print(
                        f"Error downloading PDF after {self.max_retries} attempts: {e}"
                    )
                return False


if __name__ == "__main__":
    TEST_TARGET_DIR = "tmp_repo" 
    TEST_REPO_LINK = "" 
    TEST_BRANCH = "main" 
    TEST_PDF_URL = "https://arxiv.org/pdf/2507.06849"
    
    print("--- Downloader Test Start ---")

    downloader = Downloader(target_dir=TEST_TARGET_DIR) 

    print(f"\n--- FIRST DOWNLOAD (Creates directory '{TEST_TARGET_DIR}') ---")
    success = downloader.download(TEST_REPO_LINK, branch=TEST_BRANCH)

    if success:
        print(f"\nTest passed! Repository contents are in the '{TEST_TARGET_DIR}' folder.")

        print(f"\n--- SECOND DOWNLOAD (Tests the cleanup logic on '{TEST_TARGET_DIR}') ---")
        downloader.download(TEST_REPO_LINK, branch=TEST_BRANCH)
    else:
        print("\nTest FAILED. Check the error messages above.")

    downloader.download_pdf(TEST_PDF_URL)

    print("\n--- Downloader Test Complete ---")