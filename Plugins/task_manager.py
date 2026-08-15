"""
Task Manager for queuing user downloads and uploads sequentially.
Implements a per-user queue.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

class TaskQueueManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskQueueManager, cls).__new__(cls)
            cls._instance.user_queues = {} # user_id -> asyncio.Queue
            cls._instance.user_tasks = {}  # user_id -> asyncio.Task (worker)
        return cls._instance

    async def add_task(self, user_id, target_chat_id, coro_func, *args, **kwargs):
        """Add a task for a specific user to run sequentially."""
        if user_id not in self.user_queues:
            self.user_queues[user_id] = asyncio.Queue()
            
        position = self.user_queues[user_id].qsize() + 1
        
        # We store the target_chat_id to know who to notify / cancel
        await self.user_queues[user_id].put({
            'target_chat_id': target_chat_id,
            'coro_func': coro_func,
            'args': args,
            'kwargs': kwargs
        })
        
        # Start worker for user if not running
        if user_id not in self.user_tasks or self.user_tasks[user_id].done():
            self.user_tasks[user_id] = asyncio.create_task(self._worker(user_id))
            
        return position

    async def _worker(self, user_id):
        """Background worker that processes tasks for a user sequentially."""
        logger.info(f"Started task worker for user {user_id}")
        while True:
            try:
                if self.user_queues[user_id].empty():
                    break # exit worker when queue is empty
                    
                task_dict = await self.user_queues[user_id].get()
                
                # Check for cancellation
                import Plugins.helper as helper
                target_chat_id = task_dict['target_chat_id']
                if helper.CANCEL_TASKS.get(target_chat_id, False):
                    # We don't reset CANCEL_TASKS here yet because they might want to cancel everything
                    # Wait, if they run /clean_tsk, it sets CANCEL_TASKS[target_chat_id] = True
                    # If we just skip, we should notify, but let's just let the coroutine handle it or we skip it.
                    # We will clear the whole queue in clear_queue anyway.
                    pass
                
                coro_func = task_dict['coro_func']
                args = task_dict['args']
                kwargs = task_dict['kwargs']
                
                try:
                    await coro_func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error executing queued task for user {user_id}: {e}")
                finally:
                    self.user_queues[user_id].task_done()
                    
            except Exception as e:
                logger.error(f"Worker error for user {user_id}: {e}")
                break
        
        # Worker is done
        if user_id in self.user_tasks:
            del self.user_tasks[user_id]
        logger.info(f"Finished task worker for user {user_id}")

    def clear_queue(self, target_chat_id):
        """Clear all pending tasks for a chat_id."""
        # Find which user queue has this target_chat_id
        for user_id, queue in self.user_queues.items():
            new_queue = asyncio.Queue()
            cleared = 0
            while not queue.empty():
                item = queue.get_nowait()
                if item['target_chat_id'] != target_chat_id:
                    new_queue.put_nowait(item)
                else:
                    cleared += 1
            self.user_queues[user_id] = new_queue
            if cleared > 0:
                logger.info(f"Cleared {cleared} pending tasks for chat {target_chat_id}")

task_manager = TaskQueueManager()
