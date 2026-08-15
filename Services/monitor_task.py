import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
from pyrogram.types import InputMediaPhoto, InputMediaDocument

from Database.database import Seishiro
from config import Config
from Scrapers import get_api_class          # Decoupled — no longer imports from Handlers
from Services.downloader import Downloader  # Clean Services-only import


logger = logging.getLogger(__name__)

class SubscriptionMonitor:
    def __init__(self, app):
        self.app = app
        self.is_running = False
        
    async def start(self, interval=300):
        if self.is_running: return
        self.is_running = True
        logger.info("Starting Subscription Monitor loop...")
        
        while self.is_running:
            try:
                # Wait before checking (or could use interval)
                await asyncio.sleep(interval)
                logger.info(f"Checking subscriptions at {datetime.now()}")
                await self.check_subscriptions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SubscriptionMonitor loop: {e}")
                await asyncio.sleep(60)
                
    def stop(self):
        self.is_running = False
                
    async def check_subscriptions(self):
        subs_list = await Seishiro.subs_db.get_all_subscriptions()
        if not subs_list:
            return
            
        # Group by source and URL to prevent hitting the API redundantly
        tasks_to_check = {}
        for user_doc in subs_list:
            user_id = user_doc['_id']
            subs = user_doc.get('subs', [])
            for sub in subs:
                key = (sub['source'], sub['url'])
                if key not in tasks_to_check:
                    tasks_to_check[key] = {
                        "manga_id": sub['url'],
                        "source": sub['source'],
                        "title": sub['title'],
                        "users": []
                    }
                tasks_to_check[key]["users"].append({
                    "user_id": user_id,
                    "latest_chapter": sub.get('latest_chapter', ''),
                    "auto_upload_channel_id": sub.get('auto_upload_channel_id')
                })
                
        # Check APIs
        for key, task_data in tasks_to_check.items():
            source = task_data['source']
            manga_id = task_data['manga_id']
            api_class = get_api_class(source)
            if not api_class: continue
            
            try:
                async with api_class(Config) as api:
                    # Fetch only the very first page of chapters to get the latest
                    chapters = await api.get_manga_chapters(manga_id, limit=1, offset=0)
                    if not chapters: continue
                    
                    latest_ch = chapters[0]
                    latest_ch_num = str(latest_ch['chapter'])
                    
                    # See which users need this chapter
                    users_to_update = [u for u in task_data['users'] if u['latest_chapter'] != latest_ch_num]
                    
                    if users_to_update:
                        logger.info(f"New chapter {latest_ch_num} for {task_data['title']} ({source}). Processing...")
                        await self.process_new_chapter(api, task_data, latest_ch, users_to_update)
            except Exception as e:
                logger.error(f"Error fetching updates for {task_data['title']}: {e}")
                
    async def process_new_chapter(self, api, task_data, chapter, users_to_update):
        source = task_data['source']
        manga_id = task_data['manga_id']
        manga_title = task_data['title']
        ch_num = chapter['chapter']
        ch_id = chapter['id']
        
        try:
            images = await api.get_chapter_images(ch_id)
            if not images: return
            
            # Build a temp download dir inline
            safe_title = re.sub(r'[^\w\s-]', '', manga_title)[:50].strip()
            safe_num = str(ch_num).replace('.', '_')
            download_dir = Path(tempfile.mkdtemp(prefix=f"manga_{safe_title}_{safe_num}_"))
            
            async with Downloader(Config) as downloader:
                # Setup custom referer for protected CDNs (like ToonGod)
                dl_referer = getattr(api, 'base_url', None) or getattr(api, '_base_url', None)
                dl_headers = {'Referer': dl_referer.rstrip('/') + '/'} if dl_referer else None
                
                # Create the 'images' subdir (download_images() expects this)
                chapter_img_dir = download_dir / "images"
                chapter_img_dir.mkdir(parents=True, exist_ok=True)
                
                success = await downloader.download_images(images, chapter_img_dir, headers=dl_headers)
                if not success: return
                
                # For each user, check their settings and send
                for user in users_to_update:
                    user_id = user['user_id']
                    settings = await Seishiro.settings_db.get_settings(user_id)
                    file_type = settings.get("file_type", "PDF").lower()
                    if file_type not in ["pdf", "cbz"]:
                        file_type = "pdf"
                        
                    upload_channel = settings.get("dump_channel_id")
                    
                    if not upload_channel:
                        # Fallback to DM if no dump channel configured
                        upload_channel = user_id
                    
                    file_path = await asyncio.to_thread(
                        downloader.create_chapter_file,
                        chapter_img_dir, 
                        manga_title, 
                        str(ch_num), 
                        "",  # chapter_title
                        file_type=file_type
                    )
                    
                    if file_path and file_path.exists():
                        caption = settings.get("caption_format", f"**{manga_title}**\nChapter {ch_num}")
                        if caption == "None": caption = f"**{manga_title}**\nChapter {ch_num}"
                        
                        try:
                            # 1. Send to dump channel or user (primary)
                            msg = await self.app.send_document(
                                chat_id=upload_channel,
                                document=str(file_path),
                                caption=caption
                            )
                            
                            # 2. If Auto Upload Channel is set for this sub, send it there too
                            auto_upload_channel_id = user.get("auto_upload_channel_id")
                            if auto_upload_channel_id:
                                try:
                                    if msg and msg.document:
                                        await self.app.send_document(
                                            chat_id=auto_upload_channel_id,
                                            document=msg.document.file_id,
                                            caption=caption
                                        )
                                    else:
                                        await self.app.send_document(
                                            chat_id=auto_upload_channel_id,
                                            document=str(file_path),
                                            caption=caption
                                        )
                                except Exception as e:
                                    logger.error(f"Failed to send to auto_upload_channel {auto_upload_channel_id}: {e}")
                                    
                            # Update DB
                            await Seishiro.subs_db.update_last_chapter(user_id, manga_id, source, str(ch_num))
                        except Exception as e:
                            logger.error(f"Failed to send to {upload_channel} for user {user_id}: {e}")
                        
                # Cleanup the whole directory after all users are processed
                if download_dir.exists():
                    shutil.rmtree(download_dir, ignore_errors=True)
                    
        except Exception as e:
            logger.error(f"Error processing new chapter: {e}")
