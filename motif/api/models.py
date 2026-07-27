"""
Data models for Motif GTK Theme Manager.
"""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Category:
    id: str
    name: str
    display_name: str
    type_key: str  # 'gtk', 'shell', 'icon', 'cursor', 'wallpaper', 'all'

@dataclass
class DownloadFile:
    id: str
    name: str
    url: str
    size: str = ""
    package_name: str = ""
    file_type: str = ""

@dataclass
class ThemeItem:
    id: str
    name: str
    author: str
    version: str
    summary: str
    description: str
    changelog: str
    category_id: str
    category_name: str
    type_key: str  # 'gtk', 'shell', 'icon', 'cursor', 'wallpaper', 'other'
    score: int
    downloads: int
    created: str
    changed: str = ""
    downloads24h: int = 0
    homepage: str = ""
    source_url: str = ""
    tags: List[str] = field(default_factory=list)
    preview_urls: List[str] = field(default_factory=list)
    download_files: List[DownloadFile] = field(default_factory=list)
    detail_page: str = ""
    is_favorite: bool = False

@dataclass
class InstalledTheme:
    name: str
    path: str
    type_key: str  # 'gtk', 'shell', 'icon', 'cursor', 'wallpaper'
    is_active: bool = False
    is_motif_managed: bool = False
    version: str = "Unknown"
    comment: str = ""
    author: str = ""
    variants: List[str] = field(default_factory=list)
