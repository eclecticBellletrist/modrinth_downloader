import re
import sys
from config import CONFIG

def format_line(name: str, status: str) -> str:
    padded_name = f"- {name} -"
    return f"{padded_name:<{CONFIG['MAX_NAME_LENGTH']}} {status}"

def extract_resolution(description: str) -> int:
    patterns = [
        r'(\d+)x\s*(?:resolution|текстуры|ресурспак)',
        r'(\d+)\s*x\s*\d+',
        r'(\d+)x'
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, description, re.IGNORECASE):
            return int(match.group(1))
    return 0

def check_minecraft_version(versions: list) -> bool:
    return any(version >= CONFIG["TEXTURES_CONFIG"]["MIN_MC_VERSION"] for version in versions)

def update_page_spinner(spinner_idx: int) -> int:
    spinner_chars = ['|', '/', '-', '\\']
    sys.stdout.write(f'\rОбработка... {spinner_chars[spinner_idx]}')
    sys.stdout.flush()
    return (spinner_idx + 1) % len(spinner_chars)
