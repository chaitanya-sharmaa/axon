import logging
import httpx
import os
import asyncio

log = logging.getLogger(__name__)

class WebhookNotifier:
    def __init__(self):
        self.webhook_url = os.getenv("AXON_WEBHOOK_URL")

    async def _send_async(self, payload: dict):
        if not self.webhook_url:
            return
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.webhook_url, json=payload, timeout=5.0)
                response.raise_for_status()
            except Exception as e:
                log.warning(f"Failed to send webhook notification: {e}")

    def notify(self, event_type: str, message: str, tenant_id: str):
        if not self.webhook_url:
            return
        
        payload = {
            "event_type": event_type,
            "message": message,
            "tenant_id": tenant_id
        }
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._send_async(payload))
        except RuntimeError:
            # If no running loop, we just skip it or log it
            log.warning("WebhookNotifier called outside of event loop.")

webhook_notifier = WebhookNotifier()
