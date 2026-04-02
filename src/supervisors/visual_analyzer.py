"""Visual Analyzer — uses Claude Sonnet vision to map fields and repair selectors.

Takes screenshots of portal pages, sends them to Claude with the current
selectors and fill rates, and gets back:
1. A field map: where each data point is located visually
2. Suggested selector repairs when extraction is failing
3. Confidence scores for each field detection

Triggered automatically when quality_check detects fill rates below threshold,
or manually via CLI.
"""

import base64
import json

import anthropic

from shared.config import settings
from shared.logging import get_logger
from supervisors.usage_tracker import track_usage

logger = get_logger("supervisor.visual")

ANALYSIS_PROMPT = """You are an expert web scraper analyzer. I'm showing you a screenshot of a real estate listing portal page.

## Current Selectors
These are the CSS selectors we use to extract data from this portal:
{selectors_json}

## Current Fill Rates (% of listings where we successfully extract each field)
{fill_rates_json}

## HTML Snippet (first card)
```html
{html_snippet}
```

## Task
Analyze the screenshot and HTML to:

1. **Field Map**: For each field below, describe WHERE it appears visually in the screenshot and what CSS selector would capture it:
   - price (precio)
   - bedrooms (recámaras)
   - bathrooms (baños)
   - half_bathrooms (medio baño)
   - parking_spaces (estacionamientos)
   - construction_m2 (m² construidos)
   - land_m2 (m² terreno/lote)
   - neighborhood (colonia)
   - municipality (municipio/delegación)
   - property_type (tipo de propiedad)
   - antiquity (antigüedad)
   - title (título)

2. **Broken Selectors**: Any field with fill rate below 40% likely has a broken selector. For each broken field:
   - Explain what you see in the screenshot (is the data visible?)
   - Suggest a new CSS selector based on the HTML
   - Suggest a text pattern to match (if it's text-based extraction like "3 rec.")

3. **New Fields**: Any data visible in the screenshot that we're NOT extracting yet.

Respond in JSON format:
```json
{
  "field_map": {
    "price": {"visible": true, "location": "top of card, large text", "selector": "...", "confidence": 0.95},
    ...
  },
  "repairs": [
    {"field": "bedrooms", "old_selector": "...", "new_selector": "...", "pattern": "...", "reason": "..."},
    ...
  ],
  "new_fields": [
    {"name": "...", "location": "...", "selector": "...", "description": "..."}
  ]
}
```"""

REPAIR_PROMPT = """You are an expert web scraper repair specialist. A scraper for {portal_name} has degraded performance.

## Problem
These fields have fill rates below threshold:
{problems_json}

## Current Selectors
{selectors_json}

## HTML of a search results page (first 2 cards)
```html
{html_snippet}
```

## Screenshot
I'm attaching a screenshot of the search results page showing the listing cards.

## Task
For each problematic field, analyze the HTML and screenshot to determine:
1. Is the data actually present on the page? (maybe the portal removed it)
2. If present, what CSS selector or text pattern would extract it?
3. Provide the exact repair needed.

Respond in JSON:
```json
{
  "repairs": [
    {
      "field": "bedrooms",
      "data_present": true,
      "new_selector": "li.amenities",
      "text_pattern": "recámara|recamara|rec\\\\.",
      "extraction_method": "text_match_int",
      "confidence": 0.9,
      "reason": "The bedroom count appears inside li.amenities elements as '2 Recámaras'"
    }
  ],
  "portal_changes_detected": "Description of any layout changes noticed"
}
```"""


class VisualAnalyzer:
    """Analyzes portal pages visually using Claude Sonnet."""

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    async def analyze_page(
        self,
        screenshot_bytes: bytes,
        html_snippet: str,
        selectors: dict,
        fill_rates: dict | None = None,
        portal_name: str = "",
    ) -> dict:
        """Full visual analysis of a portal page.

        Args:
            screenshot_bytes: PNG screenshot of the search results page
            html_snippet: HTML of the first 1-2 cards
            selectors: Current CSS selectors dict from config
            fill_rates: Current fill rates from quality_check (optional)
            portal_name: Name of the portal

        Returns:
            Analysis dict with field_map, repairs, and new_fields
        """
        screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

        prompt = ANALYSIS_PROMPT.format(
            selectors_json=json.dumps(selectors, indent=2, ensure_ascii=False),
            fill_rates_json=json.dumps(fill_rates or {}, indent=2),
            html_snippet=html_snippet[:4000],
        )

        logger.info(
            "visual.analyzing",
            portal=portal_name,
            screenshot_size=len(screenshot_bytes),
            html_size=len(html_snippet),
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        track_usage(self.model, response.usage.input_tokens, response.usage.output_tokens, "analysis")

        result = self._parse_json_response(response.content[0].text)

        logger.info(
            "visual.analysis_complete",
            portal=portal_name,
            fields_mapped=len(result.get("field_map", {})),
            repairs_suggested=len(result.get("repairs", [])),
            new_fields=len(result.get("new_fields", [])),
        )

        return result

    async def diagnose_and_repair(
        self,
        screenshot_bytes: bytes,
        html_snippet: str,
        selectors: dict,
        problems: list[dict],
        portal_name: str = "",
    ) -> dict:
        """Diagnose broken fields and suggest repairs.

        Args:
            screenshot_bytes: PNG screenshot
            html_snippet: HTML of first cards
            selectors: Current selectors
            problems: List of dicts with field name and current fill rate
            portal_name: Portal name

        Returns:
            Dict with repairs list and portal_changes_detected
        """
        screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

        prompt = REPAIR_PROMPT.format(
            portal_name=portal_name,
            problems_json=json.dumps(problems, indent=2),
            selectors_json=json.dumps(selectors, indent=2, ensure_ascii=False),
            html_snippet=html_snippet[:4000],
        )

        logger.info(
            "visual.diagnosing",
            portal=portal_name,
            problems=[p["field"] for p in problems],
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        track_usage(self.model, response.usage.input_tokens, response.usage.output_tokens, "repair")

        result = self._parse_json_response(response.content[0].text)

        repairs = result.get("repairs", [])
        logger.info(
            "visual.diagnosis_complete",
            portal=portal_name,
            repairs=len(repairs),
            changes=result.get("portal_changes_detected", "none"),
        )

        return result

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from Claude's response (may be wrapped in markdown)."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Extract from ```json ... ``` block
        import re
        match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning("visual.json_parse_failed", response_preview=text[:200])
        return {"field_map": {}, "repairs": [], "new_fields": []}
