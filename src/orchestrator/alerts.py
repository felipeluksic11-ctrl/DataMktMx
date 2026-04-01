"""Alerting system — notifies on scrape failures, selector issues, anti-bot detection.

Supports multiple channels:
- Log (always, structured JSON)
- Webhook (Slack, Discord, Telegram — configurable URL)
- Email (via SMTP — future)

Alerts are fire-and-forget — never block the main pipeline.
"""

import datetime
import json
from enum import StrEnum

import httpx

from shared.config.settings import settings
from shared.logging import get_logger

logger = get_logger("alerts")


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(StrEnum):
    SCRAPE_COMPLETED = "scrape_completed"
    SCRAPE_FAILED = "scrape_failed"
    SELECTORS_BROKEN = "selectors_broken"
    ANTI_BOT_DETECTED = "anti_bot_detected"
    ETL_COMPLETED = "etl_completed"
    ETL_FAILED = "etl_failed"
    EXPORT_COMPLETED = "export_completed"
    CYCLE_COMPLETED = "cycle_completed"
    WORKER_BLOCKED = "worker_blocked"


async def send_alert(
    alert_type: AlertType,
    level: AlertLevel,
    message: str,
    details: dict | None = None,
) -> None:
    """Send an alert through all configured channels."""
    alert = {
        "type": str(alert_type),
        "level": str(level),
        "message": message,
        "details": details or {},
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }

    # Always log
    log_fn = getattr(logger, level.value, logger.info)
    log_fn("alert.fired", **alert)

    # Webhook (Slack/Discord/Telegram)
    webhook_url = getattr(settings, "alert_webhook_url", None)
    if webhook_url:
        try:
            await _send_webhook(webhook_url, alert)
        except Exception:
            logger.exception("alert.webhook_failed")


async def _send_webhook(url: str, alert: dict) -> None:
    """Send alert to a webhook URL (Slack-compatible format)."""
    emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨",
    }.get(alert["level"], "📢")

    payload = {
        "text": f"{emoji} *{alert['type']}* — {alert['message']}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{alert['type']}*\n{alert['message']}"
                }
            }
        ]
    }

    if alert.get("details"):
        detail_text = "\n".join(f"• {k}: {v}" for k, v in alert["details"].items())
        payload["blocks"].append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"```{detail_text}```"}
        })

    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, timeout=10)


# ──────────────── Convenience functions ────────────────


async def alert_scrape_completed(portal: str, listings: int, duration_s: float) -> None:
    await send_alert(
        AlertType.SCRAPE_COMPLETED, AlertLevel.INFO,
        f"{portal}: {listings} listings scraped in {duration_s:.0f}s",
        {"portal": portal, "listings": listings, "duration_s": duration_s},
    )


async def alert_scrape_failed(portal: str, error: str) -> None:
    await send_alert(
        AlertType.SCRAPE_FAILED, AlertLevel.ERROR,
        f"{portal}: scrape failed — {error[:100]}",
        {"portal": portal, "error": error[:500]},
    )


async def alert_selectors_broken(portal: str, details: str) -> None:
    await send_alert(
        AlertType.SELECTORS_BROKEN, AlertLevel.CRITICAL,
        f"{portal}: selectores rotos — necesita repair",
        {"portal": portal, "details": details[:500]},
    )


async def alert_cycle_completed(summary: dict) -> None:
    scouts = len(summary.get("scouts", []))
    plans = len(summary.get("plans", []))
    errors = len(summary.get("errors", []))
    etl = summary.get("etl", {})
    cleaned = etl.get("cleaned", 0) if etl else 0

    level = AlertLevel.ERROR if errors > 0 else AlertLevel.INFO
    await send_alert(
        AlertType.CYCLE_COMPLETED, level,
        f"Ciclo completo: {scouts} scouts, {plans} plans, {cleaned} cleaned, {errors} errors",
        {"scouts": scouts, "plans": plans, "cleaned": cleaned, "errors": errors},
    )
