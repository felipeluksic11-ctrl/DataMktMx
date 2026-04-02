"""Spot Checker — validates extraction accuracy against screenshots.

Every N listings, takes a screenshot of the current page and asks Claude
to read the data visually. Then compares Claude's reading against what
the parser extracted. Logs mismatches as warnings.

This catches subtle bugs like:
- m² terreno vs m² construcción swapped
- Price parsed from wrong element
- Location fields in wrong columns
"""

import base64
import json

import anthropic

from shared.config import settings
from shared.logging import get_logger
from supervisors.usage_tracker import track_usage

logger = get_logger("supervisor.spot_check")

SPOT_CHECK_PROMPT = """You are verifying a web scraper's data extraction accuracy.

I'm showing you a screenshot of a real estate listing card from {portal_name}.

The scraper extracted these values from this card:
```json
{extracted_json}
```

## Task
Look at the screenshot and read the ACTUAL values shown for this listing. Then compare with what the scraper extracted.

For each field, report:
- **match**: the extracted value matches what's visible
- **mismatch**: the extracted value is wrong (include what it should be)
- **missing**: the data is visible but the scraper got null
- **not_visible**: the field isn't shown on the card (null is correct)

Respond in JSON:
```json
{{
  "checks": {{
    "price": {{"status": "match", "extracted": 3700000, "actual": 3700000}},
    "bedrooms": {{"status": "missing", "extracted": null, "actual": 3}},
    "construction_m2": {{"status": "mismatch", "extracted": 165, "actual": null, "note": "165 is actually land_m2, shown as 'm² lote'"}},
    ...
  }},
  "accuracy_score": 0.85,
  "issues": ["construction_m2 and land_m2 are swapped", "bedrooms not being extracted"]
}}
```

Only check fields that are relevant for a card view: price, bedrooms, bathrooms, parking_spaces, construction_m2, land_m2, property_type, neighborhood, municipality, state."""


class SpotChecker:
    """Validates extraction accuracy by comparing parsed data against screenshots."""

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-haiku-4-5-20251001"  # Haiku for cost efficiency (~$0.002/check)

    async def verify_extraction(
        self,
        screenshot_bytes: bytes,
        extracted_data: dict,
        portal_name: str,
    ) -> dict:
        """Compare extracted data against what Claude sees in the screenshot.

        Args:
            screenshot_bytes: PNG screenshot of the card/page
            extracted_data: What the parser extracted (subset of ScrapedItem fields)
            portal_name: Portal name for context

        Returns:
            Verification result with per-field status and accuracy score
        """
        screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

        # Clean extracted data for readability
        clean_data = {k: v for k, v in extracted_data.items() if v is not None}

        prompt = SPOT_CHECK_PROMPT.format(
            portal_name=portal_name,
            extracted_json=json.dumps(clean_data, indent=2, ensure_ascii=False),
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
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

        track_usage(
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            purpose="spot_check",
        )

        result = self._parse_json(response.content[0].text)

        # Log results
        accuracy = result.get("accuracy_score", 0)
        issues = result.get("issues", [])

        if accuracy >= 0.9:
            logger.info(
                "spot_check.passed",
                portal=portal_name,
                accuracy=accuracy,
            )
        else:
            logger.warning(
                "spot_check.issues_found",
                portal=portal_name,
                accuracy=accuracy,
                issues=issues,
            )

        # Log individual mismatches
        for field, check in result.get("checks", {}).items():
            if check.get("status") in ("mismatch", "missing"):
                logger.warning(
                    "spot_check.field_mismatch",
                    portal=portal_name,
                    field=field,
                    status=check["status"],
                    extracted=check.get("extracted"),
                    actual=check.get("actual"),
                    note=check.get("note", ""),
                )

        return result

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from response."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        import re
        match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {"checks": {}, "accuracy_score": 0, "issues": ["Failed to parse response"]}
