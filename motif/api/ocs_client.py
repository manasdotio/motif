"""
OCS API v1 client for gnome-look.org / opendesktop.org.
"""
import re
import html
import logging
from typing import List, Dict, Optional, Tuple, Any
import httpx

from motif.api.models import Category, ThemeItem, DownloadFile

logger = logging.getLogger(__name__)

# Default known category IDs as fallback if network category fetching fails
DEFAULT_CATEGORY_MAPPINGS = {
    "gtk": ["135", "366"],      # GTK 3.x/4.x Theme/Style, Gnome/GTK
    "shell": ["134"],           # GNOME Shell Theme
    "icon": ["132", "386"],     # KDE Icon Theme, Icons
    "cursor": ["107"],          # X11 Mouse Theme
    "wallpaper": ["300", "295"] # Wallpapers Gnome, Wallpapers
}

PRIMARY_BASE_URL = "https://api.gnome-look.org/ocs/v1/"
FALLBACK_BASE_URL = "https://api.opendesktop.org/ocs/v1/"

class OCSClientError(Exception):
    """Exception raised for OCS API errors."""
    pass

class OCSClient:
    def __init__(self, base_url: str = PRIMARY_BASE_URL, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.user_agent = "MotifThemeManager/1.0 (Linux; GNOME)"
        self._categories_cache: List[Category] = []
        self._category_map: Dict[str, Category] = {}

    def _get_client(self) -> httpx.Client:
        return httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            follow_redirects=True
        )

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Performs a GET request to OCS API with primary base_url and fallback."""
        params = params or {}
        params["format"] = "json"

        urls_to_try = [
            f"{self.base_url}{endpoint}",
            f"{FALLBACK_BASE_URL}{endpoint}"
        ]

        last_exception = None
        for url in urls_to_try:
            try:
                with httpx.Client(headers={"User-Agent": self.user_agent}, timeout=self.timeout, follow_redirects=True) as client:
                    resp = client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        # Check OCS status code
                        status = data.get("status", "")
                        statuscode = data.get("statuscode")
                        if status == "error" or (statuscode and int(statuscode) >= 400):
                            msg = data.get("message", "API returned error status")
                            raise OCSClientError(f"OCS API Error: {msg}")
                        return data
                    elif resp.status_code in (404, 410):
                        continue
                    else:
                        resp.raise_for_status()
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                last_exception = e

        raise OCSClientError(f"Failed to connect to OCS API: {last_exception}")

    @staticmethod
    def _strip_html(raw_html: str) -> str:
        """Strips HTML tags and unescapes entities for clean GTK label rendering."""
        if not raw_html:
            return ""
        clean_text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.IGNORECASE)
        clean_text = re.sub(r'</p>', '\n\n', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = html.unescape(clean_text)
        return clean_text.strip()

    @staticmethod
    def _detect_type_key(name: str, cat_id: str) -> str:
        """Determines theme type key from category name and ID."""
        name_lower = name.lower()
        if cat_id in DEFAULT_CATEGORY_MAPPINGS["gtk"] or "gtk" in name_lower:
            return "gtk"
        elif cat_id in DEFAULT_CATEGORY_MAPPINGS["shell"] or "shell" in name_lower:
            return "shell"
        elif cat_id in DEFAULT_CATEGORY_MAPPINGS["cursor"] or "cursor" in name_lower or "mouse" in name_lower:
            return "cursor"
        elif cat_id in DEFAULT_CATEGORY_MAPPINGS["icon"] or "icon" in name_lower:
            return "icon"
        elif cat_id in DEFAULT_CATEGORY_MAPPINGS["wallpaper"] or "wallpaper" in name_lower:
            return "wallpaper"
        return "other"

    def fetch_categories(self) -> List[Category]:
        """Fetches and caches categories from OCS API."""
        try:
            res = self._request("content/categories")
            raw_cats = res.get("data", [])
            categories = []
            for item in raw_cats:
                cat_id = str(item.get("id", ""))
                name = item.get("name", "")
                display_name = item.get("display_name") or name
                type_key = self._detect_type_key(name, cat_id)
                cat = Category(
                    id=cat_id,
                    name=name,
                    display_name=display_name,
                    type_key=type_key
                )
                categories.append(cat)
                self._category_map[cat_id] = cat
            self._categories_cache = categories
            return categories
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            # Return standard fallback categories
            fallbacks = [
                Category(id="135", name="GTK 3.x/4.x Theme", display_name="GTK Themes", type_key="gtk"),
                Category(id="134", name="GNOME Shell Theme", display_name="Shell Themes", type_key="shell"),
                Category(id="132", name="KDE Icon Theme", display_name="Icon Themes", type_key="icon"),
                Category(id="107", name="X11 Mouse Theme", display_name="Cursor Themes", type_key="cursor"),
                Category(id="300", name="Wallpapers Gnome", display_name="Wallpapers", type_key="wallpaper"),
            ]
            self._categories_cache = fallbacks
            for c in fallbacks:
                self._category_map[c.id] = c
            return fallbacks

    def get_category_ids_for_type(self, type_key: str) -> List[str]:
        """Returns list of category IDs matching a type key ('gtk', 'shell', 'icon', 'cursor', 'wallpaper')."""
        if not self._categories_cache:
            self.fetch_categories()
        ids = [c.id for c in self._categories_cache if c.type_key == type_key]
        if not ids and type_key in DEFAULT_CATEGORY_MAPPINGS:
            ids = DEFAULT_CATEGORY_MAPPINGS[type_key]
        return ids

    def get_all_gnome_category_ids(self) -> List[str]:
        """Returns list of all category IDs that belong to GNOME theme types."""
        all_ids = []
        for type_key in ("gtk", "shell", "icon", "cursor", "wallpaper"):
            all_ids.extend(self.get_category_ids_for_type(type_key))
        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for cid in all_ids:
            if cid not in seen:
                seen.add(cid)
                unique_ids.append(cid)
        return unique_ids

    def search_content(
        self,
        category_type: str = "all",
        category_id: Optional[str] = None,
        search_query: Optional[str] = None,
        sort_mode: str = "rating",  # 'rating', 'downloads', 'newest', 'name'
        page: int = 1,
        page_size: int = 30
    ) -> Tuple[List[ThemeItem], int]:
        """
        Searches content across specified categories or search terms.
        Returns tuple of (items_list, total_items_count).
        """
        params: Dict[str, Any] = {
            "page": page - 1,  # OCS API is 0-indexed for page
            "pagesize": page_size,
        }

        # Map sort mode
        sort_map = {
            "relevance": "relevance",
            "rating": "score",
            "downloads": "downloads",
            "newest": "new",
            "name": "alpha"
        }
        params["sortmode"] = sort_map.get(sort_mode, "relevance" if search_query else "score")

        # Category filter: restrict to GNOME categories
        if category_id:
            params["categories"] = category_id
        elif category_type and category_type != "all":
            cat_ids = self.get_category_ids_for_type(category_type)
            if cat_ids:
                params["categories"] = "x".join(cat_ids)  # OCS API joins multiple categories with 'x'
        else:
            # For "all", restrict API request to GNOME-compatible category IDs
            gnome_cat_ids = self.get_all_gnome_category_ids()
            if gnome_cat_ids:
                params["categories"] = "x".join(gnome_cat_ids)

        if search_query and search_query.strip():
            params["search"] = search_query.strip()

        res = self._request("content/data", params=params)
        raw_items = res.get("data", [])
        total_items = 0
        try:
            total_items = int(res.get("totalitems", len(raw_items)))
        except (ValueError, TypeError):
            total_items = len(raw_items)

        items = [self._parse_theme_item(raw) for raw in raw_items]
        # Post-filter: remove any non-GNOME items (type_key == 'other')
        gnome_items = [item for item in items if item.type_key != "other"]
        return gnome_items, total_items

    def get_content_detail(self, content_id: str) -> ThemeItem:
        """Fetches full detail for a single content item."""
        res = self._request(f"content/data/{content_id}")
        raw_data = res.get("data", [])
        if not raw_data:
            raise OCSClientError(f"Content item {content_id} not found")
        return self._parse_theme_item(raw_data[0])

    def get_person_detail(self, person_id: str) -> Dict[str, Any]:
        """Fetches user profile details for a given author handle."""
        try:
            res = self._request(f"person/data/{person_id}")
            raw_data = res.get("data", [])
            if raw_data and isinstance(raw_data, list):
                return raw_data[0]
        except Exception as e:
            logger.warning(f"Failed fetching person data for {person_id}: {e}")
        return {"personid": person_id, "avatarpic": f"https://www.opendesktop.org/avatar/{person_id}"}

    def get_avatar_url(self, person_id: str) -> str:
        """Returns avatar image URL for a given author handle."""
        return f"https://www.opendesktop.org/avatar/{person_id}"

    def _parse_theme_item(self, raw: Dict[str, Any]) -> ThemeItem:
        """Parses raw OCS json dict into ThemeItem object."""
        item_id = str(raw.get("id", ""))
        name = self._strip_html(str(raw.get("name", "Untitled")))
        
        author = raw.get("personid")
        if not author:
            details_field = raw.get("details")
            if isinstance(details_field, dict):
                author = details_field.get("personid")
        author = str(author or "Unknown")
        version = raw.get("version", "1.0")
        cat_id = str(raw.get("typeid", ""))
        cat_name = raw.get("typename", "")

        type_key = self._detect_type_key(cat_name, cat_id)

        # Parse previews
        previews = []
        for i in range(1, 5):
            url = raw.get(f"previewpic{i}") or raw.get(f"preview{i}") or raw.get(f"smallpreviewpic{i}")
            if url and isinstance(url, str) and url.startswith("http"):
                previews.append(url)

        # Parse downloads
        downloads = []
        for i in range(1, 11):
            link = raw.get(f"downloadlink{i}")
            if link and isinstance(link, str) and link.startswith("http"):
                dl_name = raw.get(f"downloadname{i}") or f"File {i}"
                dl_size = raw.get(f"downloadsize{i}") or ""
                pkg_name = raw.get(f"downloadpackagename{i}") or ""
                file_type = raw.get(f"downloadtype{i}") or ""
                downloads.append(DownloadFile(
                    id=f"{item_id}-{i}",
                    name=self._strip_html(dl_name),
                    url=link,
                    size=str(dl_size),
                    package_name=pkg_name,
                    file_type=file_type
                ))

        score = 0
        try:
            score = int(raw.get("score", 0))
        except (ValueError, TypeError):
            pass

        dl_count = 0
        try:
            dl_count = int(raw.get("downloads", 0))
        except (ValueError, TypeError):
            pass

        dl24h_count = 0
        try:
            dl24h_count = int(raw.get("downloads24h") or raw.get("downloads_24h") or raw.get("downloads24") or 0)
        except (ValueError, TypeError):
            pass

        summary = self._strip_html(raw.get("summary", ""))
        description = self._strip_html(raw.get("description", ""))
        changelog = self._strip_html(raw.get("changelog", ""))

        homepage = str(raw.get("homepage") or "").strip()
        source_url = str(raw.get("feedbackurl") or "").strip()
        if not source_url and (description or summary):
            match = re.search(r'https?://(?:www\.)?(?:github\.com|gitlab\.com|codeberg\.org)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', description + " " + summary)
            if match:
                source_url = match.group(0)

        raw_tags = raw.get("tags") or ""
        tags = [t.strip() for t in str(raw_tags).split(",") if t and t.strip() and "##" not in t]

        return ThemeItem(
            id=item_id,
            name=name,
            author=author,
            version=version,
            summary=summary,
            description=description,
            changelog=changelog,
            category_id=cat_id,
            category_name=cat_name,
            type_key=type_key,
            score=score,
            downloads=dl_count,
            created=str(raw.get("created") or ""),
            changed=str(raw.get("changed") or ""),
            downloads24h=dl24h_count,
            homepage=homepage,
            source_url=source_url,
            tags=tags,
            preview_urls=previews,
            download_files=downloads,
            detail_page=raw.get("detailpage", "")
        )
