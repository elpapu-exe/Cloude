"""Select the exact Linux source tree exercised by compiled helper regressions."""
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
override = os.environ.get('CHATGPT_TEST_SOURCE_ROOT')
SOURCE_ROOT = Path(override) if override else PROJECT_ROOT / 'kernel-source/linux'
if not SOURCE_ROOT.is_absolute():
    SOURCE_ROOT = PROJECT_ROOT / SOURCE_ROOT
SOURCE_ROOT = SOURCE_ROOT.resolve(strict=True)
if not SOURCE_ROOT.is_dir():
    raise RuntimeError(f'Test source root is not a directory: {SOURCE_ROOT}')
