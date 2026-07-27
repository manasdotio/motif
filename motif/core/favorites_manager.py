"""
Favorites manager for storing and loading starred/favorited theme items.
"""
import os
import json
import logging
from typing import List, Set, Dict, Optional

from motif.api.models import ThemeItem, DownloadFile

logger = logging.getLogger(__name__)

class FavoritesManager:
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = os.path.join(os.path.expanduser("~"), ".config", "motif")
        
        self.filepath = os.path.join(self.config_dir, "favorites.json")
        self._favorites: Dict[str, ThemeItem] = {}
        self.load_favorites()

    def load_favorites(self):
        """Loads favorite theme items from JSON configuration file."""
        self._favorites.clear()
        if not os.path.exists(self.filepath):
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item_dict in data.get("favorites", []):
                    item = self._dict_to_theme_item(item_dict)
                    if item and item.id:
                        item.is_favorite = True
                        self._favorites[item.id] = item
        except Exception as e:
            logger.error(f"Error loading favorites from {self.filepath}: {e}")

    def save_favorites(self):
        """Saves favorite theme items to JSON configuration file."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            data_list = [self._theme_item_to_dict(item) for item in self._favorites.values()]
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"favorites": data_list}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving favorites to {self.filepath}: {e}")

    def is_favorite(self, item_id: str) -> bool:
        """Returns True if the theme item ID is in favorites."""
        return item_id in self._favorites

    def add_favorite(self, item: ThemeItem):
        """Adds a ThemeItem to favorites."""
        item.is_favorite = True
        self._favorites[item.id] = item
        self.save_favorites()

    def remove_favorite(self, item_id: str):
        """Removes a theme item from favorites by ID."""
        if item_id in self._favorites:
            del self._favorites[item_id]
            self.save_favorites()

    def toggle_favorite(self, item: ThemeItem) -> bool:
        """Toggles favorite status for a ThemeItem. Returns new is_favorite status."""
        if item.id in self._favorites:
            self.remove_favorite(item.id)
            item.is_favorite = False
            return False
        else:
            self.add_favorite(item)
            return True

    def get_favorites(self) -> List[ThemeItem]:
        """Returns list of all favorited ThemeItem objects."""
        return list(self._favorites.values())

    def get_favorite_ids(self) -> Set[str]:
        """Returns set of all favorited item IDs."""
        return set(self._favorites.keys())

    @staticmethod
    def _theme_item_to_dict(item: ThemeItem) -> Dict:
        downloads = [
            {
                "id": d.id,
                "name": d.name,
                "url": d.url,
                "size": d.size,
                "package_name": d.package_name,
                "file_type": d.file_type
            }
            for d in item.download_files
        ]
        return {
            "id": item.id,
            "name": item.name,
            "author": item.author,
            "version": item.version,
            "summary": item.summary,
            "description": item.description,
            "changelog": item.changelog,
            "category_id": item.category_id,
            "category_name": item.category_name,
            "type_key": item.type_key,
            "score": item.score,
            "downloads": item.downloads,
            "created": item.created,
            "preview_urls": item.preview_urls,
            "download_files": downloads,
            "detail_page": item.detail_page,
            "is_favorite": True
        }

    @staticmethod
    def _dict_to_theme_item(data: Dict) -> Optional[ThemeItem]:
        try:
            downloads = [
                DownloadFile(
                    id=d.get("id", ""),
                    name=d.get("name", ""),
                    url=d.get("url", ""),
                    size=d.get("size", ""),
                    package_name=d.get("package_name", ""),
                    file_type=d.get("file_type", "")
                )
                for d in data.get("download_files", [])
            ]
            return ThemeItem(
                id=str(data.get("id", "")),
                name=data.get("name", ""),
                author=data.get("author", ""),
                version=data.get("version", "1.0"),
                summary=data.get("summary", ""),
                description=data.get("description", ""),
                changelog=data.get("changelog", ""),
                category_id=str(data.get("category_id", "")),
                category_name=data.get("category_name", ""),
                type_key=data.get("type_key", "gtk"),
                score=int(data.get("score", 0)),
                downloads=int(data.get("downloads", 0)),
                created=data.get("created", ""),
                preview_urls=data.get("preview_urls", []),
                download_files=downloads,
                detail_page=data.get("detail_page", ""),
                is_favorite=True
            )
        except Exception as e:
            logger.error(f"Error parsing favorite item dict: {e}")
            return None
