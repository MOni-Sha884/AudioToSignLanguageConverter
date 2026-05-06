"""
Sign File Manager for IntelliSign
===================================
Loads and manages the available .sigml files from the SignFiles directory.
Provides fast lookup for the translation engine.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from django.conf import settings


def get_available_signs() -> List[str]:
    """
    Return list of all available .mp4 filenames (without path).
    """
    sign_dir = settings.SIGN_FILES_DIR
    if not sign_dir.exists():
        return []

    signs = []
    for f in sign_dir.iterdir():
        if f.suffix.lower() == '.mp4':
            signs.append(f.name)
    return sorted(signs)


def get_sign_names_set() -> set:
    """Return a set of sign names (without .mp4 extension, lowercase)."""
    return {s[:-4].lower() for s in get_available_signs()}


def get_sigml_json() -> List[Dict]:
    """
    Return the sigml list in the same format used by the legacy JS player.
    Each entry: {sid, name, fileName}
    """
    signs = get_available_signs()
    result = []
    for i, filename in enumerate(signs):
        name = filename[:-4].lower()  # strip .mp4, lowercase
        result.append({
            'sid': i + 1,
            'name': name,
            'fileName': filename,
        })
    return result


def sign_exists(word: str) -> bool:
    """Check if a sign exists for the given word."""
    word = word.lower().strip('.,!?')
    return word in get_sign_names_set()


def get_sign_file(word: str) -> Optional[str]:
    """Return the video filename for a word, or None if not found."""
    word = word.lower().strip('.,!?')
    sign_dir = settings.SIGN_FILES_DIR

    # Try exact match
    candidate = sign_dir / f"{word}.mp4"
    if candidate.exists():
        return f"{word}.mp4"

    # Try capitalized
    candidate = sign_dir / f"{word.capitalize()}.mp4"
    if candidate.exists():
        return f"{word.capitalize()}.mp4"
        
    # Try uppercase
    candidate = sign_dir / f"{word.upper()}.mp4"
    if candidate.exists():
        return f"{word.upper()}.mp4"

    return None
