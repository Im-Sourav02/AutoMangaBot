import logging

logger = logging.getLogger(__name__)

class UserSettingsDB:
    def __init__(self, database):
        self.col = database['user_settings']

    async def get_settings(self, user_id: int) -> dict:
        try:
            settings = await self.col.find_one({"_id": int(user_id)})
            if not settings:
                settings = {
                    "_id": int(user_id),
                    "dump_channel_id": None,
                    "file_type": "PDF", # Default to PDF as requested
                    "caption_format": "None",
                    "banner_url": None,
                    "thumbnail_enabled": True,
                    "compress_quality": "High"
                }
                await self.col.insert_one(settings)
            return settings
        except Exception as e:
            logger.error(f"Error getting settings for {user_id}: {e}")
            return {}

    async def update_setting(self, user_id: int, key: str, value: any) -> bool:
        try:
            res = await self.col.update_one(
                {"_id": int(user_id)},
                {"$set": {key: value}},
                upsert=True
            )
            return res.modified_count > 0 or res.upserted_id is not None
        except Exception as e:
            logger.error(f"Error updating setting {key} for {user_id}: {e}")
            return False
