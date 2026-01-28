"""
UI Context Manager for tracking frontend state and preventing redundancy.
Implements AGUI-like protocol for frontend-backend state synchronization.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ElementInfo:
    """Information about a visible UI element."""
    id: str
    element_type: str = "flashcard"
    title: str = ""
    visible_since: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ViewportInfo:
    """Information about the user's viewport."""
    screen: str = "desktop"  # mobile | desktop | tablet
    width: int = 1920
    height: int = 1080


@dataclass
class PageContext:
    """Current page context information."""
    route: str = "/"
    section: str = ""


class UIContextManager:
    """
    Manages UI state synchronization between frontend and backend.
    
    Tracks:
    - Viewport information (screen type, dimensions)
    - Active elements currently visible to the user
    - Page context (route, section)
    
    Provides:
    - Redundancy detection via is_visible()
    - LLM prompt generation with current UI state
    """
    
    def __init__(self):
        self.viewport = ViewportInfo()
        self.active_elements: dict[str, ElementInfo] = {}
        self.page_context = PageContext()
        self.capabilities: dict[str, bool] = {
            "supportsRichUI": False,
            "supportsDynamicMedia": False,
        }
        self._last_sync_timestamp: int = 0
    
    def update_from_sync(self, payload: dict) -> None:
        """
        Process incoming ui.context_sync message from frontend.
        
        Expected payload structure:
        {
            "type": "ui.context_sync",
            "viewport": {"screen": "desktop", "width": 1920, "height": 1080},
            "active_elements": [
                {"id": "...", "type": "flashcard", "title": "..."}
            ],
            "page_context": {"route": "/", "section": "hero"}
        }
        """
        if not isinstance(payload, dict):
            logger.warning("Invalid ui.context_sync payload: not a dict")
            return
        
        # Check message type
        msg_type = payload.get("type", "")
        if msg_type != "ui.context_sync":
            logger.debug(f"Ignoring message type: {msg_type}")
            return
        
        # Update viewport
        viewport_data = payload.get("viewport", {})
        if isinstance(viewport_data, dict):
            self.viewport = ViewportInfo(
                screen=viewport_data.get("screen", "desktop"),
                width=viewport_data.get("width", 1920),
                height=viewport_data.get("height", 1080),
            )
            logger.debug(f"Viewport updated: {self.viewport}")
        
        # Update active elements (full replacement)
        elements_data = payload.get("active_elements", [])
        if isinstance(elements_data, list):
            self.active_elements.clear()
            for elem in elements_data:
                if isinstance(elem, dict) and "id" in elem:
                    elem_id = elem["id"]
                    self.active_elements[elem_id] = ElementInfo(
                        id=elem_id,
                        element_type=elem.get("type", "flashcard"),
                        title=elem.get("title", ""),
                        visible_since=elem.get("visible_since", 0),
                        metadata={k: v for k, v in elem.items() 
                                  if k not in ("id", "type", "title", "visible_since")},
                    )
            logger.info(f"Active elements updated: {len(self.active_elements)} items")
        
        # Update page context
        page_data = payload.get("page_context", {})
        if isinstance(page_data, dict):
            self.page_context = PageContext(
                route=page_data.get("route", "/"),
                section=page_data.get("section", ""),
            )
            logger.debug(f"Page context updated: {self.page_context}")
        
        # Update capabilities
        self.capabilities["supportsRichUI"] = payload.get("supportsRichUI", False)
        self.capabilities["supportsDynamicMedia"] = payload.get("supportsDynamicMedia", False)
        if self.capabilities["supportsRichUI"] or self.capabilities["supportsDynamicMedia"]:
            logger.info("Frontend capabilities: %s", self.capabilities)
        
        self._last_sync_timestamp = payload.get("timestamp", 0)
    
    def is_visible(self, element_id: str) -> bool:
        """Check if an element with the given ID is currently visible."""
        return element_id in self.active_elements
    
    def is_title_visible(self, title: str) -> bool:
        """Check if an element with a similar title is currently visible."""
        title_lower = title.lower().strip()
        for elem in self.active_elements.values():
            if elem.title.lower().strip() == title_lower:
                return True
        return False
    
    def get_visible_ids(self) -> set[str]:
        """Get all currently visible element IDs."""
        return set(self.active_elements.keys())
    
    def get_visible_titles(self) -> set[str]:
        """Get all currently visible element titles."""
        return {elem.title for elem in self.active_elements.values() if elem.title}
    
    def generate_context_prompt(self) -> str:
        """
        Generate a markdown string describing current UI state for LLM injection.
        """
        lines: list[str] = []
        lines.append("\n## CURRENT UI STATE (What the user can see)")
        
        # Viewport info
        lines.append(f"- Device: {self.viewport.screen} ({self.viewport.width}x{self.viewport.height})")
        lines.append(f"- Current Page: {self.page_context.route}")
        if self.page_context.section:
            lines.append(f"- Active Section: {self.page_context.section}")
        
        # Active elements
        if self.active_elements:
            lines.append(f"- Visible Cards ({len(self.active_elements)}):")
            for elem in self.active_elements.values():
                lines.append(f"  * [{elem.id}] {elem.title}")
        else:
            lines.append("- No cards currently visible")
        
        lines.append("")
        lines.append("## FRONTEND CAPABILITIES")
        lines.append(f"- Rich UI (Visual Intent/Animations): {'Supported' if self.capabilities.get('supportsRichUI') else 'Not Supported'}")
        lines.append(f"- Dynamic Media (Keyword Images): {'Supported' if self.capabilities.get('supportsDynamicMedia') else 'Not Supported'}")

        lines.append("")
        lines.append("## REDUNDANCY RULE")
        lines.append("DO NOT generate information for cards already visible above.")
        lines.append("If the user asks about something already shown, acknowledge it's visible and offer more details.")
        
        return "\n".join(lines)
    
    def filter_redundant_cards(self, cards: list[dict]) -> list[dict]:
        """
        Filter out cards that are already visible on screen.
        
        Checks both:
        - Exact ID match (if card has 'id' or 'card_id')
        - Title match (case-insensitive)
        """
        filtered: list[dict] = []
        visible_ids = self.get_visible_ids()
        visible_titles = {t.lower() for t in self.get_visible_titles()}
        
        for card in cards:
            # Check ID
            card_id = card.get("id") or card.get("card_id", "")
            if card_id and card_id in visible_ids:
                logger.info(f"Filtering redundant card by ID: {card_id}")
                continue
            
            # Check title
            card_title = card.get("title", "").lower().strip()
            if card_title and card_title in visible_titles:
                logger.info(f"Filtering redundant card by title: {card_title}")
                continue
            
            filtered.append(card)
        
        if len(filtered) < len(cards):
            logger.info(f"Filtered {len(cards) - len(filtered)} redundant cards")
        
        return filtered
    
    def to_dict(self) -> dict[str, Any]:
        """Export current state as a dictionary."""
        return {
            "viewport": {
                "screen": self.viewport.screen,
                "width": self.viewport.width,
                "height": self.viewport.height,
            },
            "active_elements": [
                {
                    "id": elem.id,
                    "type": elem.element_type,
                    "title": elem.title,
                }
                for elem in self.active_elements.values()
            ],
            "page_context": {
                "route": self.page_context.route,
                "section": self.page_context.section,
            },
        }
