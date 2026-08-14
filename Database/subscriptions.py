import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SubscriptionDB:
    def __init__(self, database):
        # We store subscriptions per user.
        # Format: { "_id": user_id, "subs": [ { "url": "...", "title": "...", "latest_chapter": "...", "source": "...", ... } ] }
        self.col = database['subscriptions']

    async def add_subscription(self, user_id: int, manga_data: dict, source: str) -> bool:
        try:
            sub = {
                "url": manga_data.get("id") or manga_data.get("url"),
                "title": manga_data.get("title", "Unknown"),
                "latest_chapter": manga_data.get("latest_chapter", ""),
                "source": source,
                "auto_upload_channel_id": manga_data.get("auto_upload_channel_id"),
                "created_at": datetime.utcnow()
            }
            
            # Use $addToSet to avoid exact duplicates, but if we need to update, we can just push or pull+push
            # It's better to pull existing and then push to update it
            await self.col.update_one(
                {"_id": int(user_id)},
                {"$pull": {"subs": {"url": sub["url"], "source": source}}},
                upsert=True
            )
            await self.col.update_one(
                {"_id": int(user_id)},
                {"$push": {"subs": sub}}
            )
            return True
        except Exception as e:
            logger.error(f"Error adding subscription for {user_id}: {e}")
            return False

    async def remove_subscription(self, user_id: int, manga_id: str, source: str) -> bool:
        try:
            res = await self.col.update_one(
                {"_id": int(user_id)},
                {"$pull": {"subs": {"url": manga_id, "source": source}}}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Error removing subscription {manga_id} for {user_id}: {e}")
            return False

    async def clear_all_subscriptions(self, user_id: int) -> bool:
        try:
            res = await self.col.delete_one({"_id": int(user_id)})
            return res.deleted_count > 0
        except Exception as e:
            logger.error(f"Error clearing subscriptions for {user_id}: {e}")
            return False

    async def get_user_subscriptions(self, user_id: int) -> List[dict]:
        try:
            doc = await self.col.find_one({"_id": int(user_id)})
            if doc:
                return doc.get("subs", [])
            return []
        except Exception as e:
            logger.error(f"Error getting subscriptions for {user_id}: {e}")
            return []

    async def update_last_chapter(self, user_id: int, manga_id: str, source: str, chapter_num: str) -> bool:
        try:
            res = await self.col.update_one(
                {"_id": int(user_id), "subs.url": manga_id, "subs.source": source},
                {"$set": {"subs.$.latest_chapter": str(chapter_num)}}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating last chapter for {manga_id} (user {user_id}): {e}")
            return False

    async def get_all_subscriptions(self) -> List[dict]:
        """Returns all documents for the monitoring loop."""
        try:
            cursor = self.col.find({})
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error getting all subscriptions: {e}")
            return []

    async def update_auto_upload_channel_id(self, user_id: int, manga_url: str, channel_id: int) -> bool:
        """Update auto upload channel id for a subscription"""
        try:
            res = await self.col.update_one(
                {'_id': int(user_id), 'subs.url': manga_url},
                {'$set': {'subs.$.auto_upload_channel_id': channel_id}}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating sub channel: {e}")
            return False
