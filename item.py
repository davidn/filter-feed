from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, TypeVar
from email.utils import parsedate_to_datetime

import xml.etree.ElementTree as ET

@dataclass
class Item:
    title: Optional[str]
    date: Optional[datetime]
    description: Optional[str]
    T = TypeVar('T')

    @classmethod
    def _content(cls, item: ET.Element, tag: str, c: Callable[[str], T]=str) -> Optional[T]:
        el = item.find(tag)
        return None if el is None else c(el.text)

    @classmethod
    def fromRssItem(cls, item: ET.Element) -> 'Item':
        return Item(
                title=cls._content(item, "title"),
                date=cls._content(item, "pubDate", parsedate_to_datetime),
                description=cls._content(item, "description")
                )

    @classmethod
    def fromAtomEntry(cls, item: ET.Element) -> 'Item':
        return Item(
                title=cls._content(item, "{http://www.w3.org/2005/Atom}title"),
                date=cls._content(item, "{http://www.w3.org/2005/Atom}updated", datetime.fromisoformat),
                description=cls._content(item, "{http://www.w3.org/2005/Atom}summary")
                )
