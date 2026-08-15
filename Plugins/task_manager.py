"""
Task Manager for queuing user downloads and uploads sequentially.
Implements a per-user asyncio.Queue with a dedicated worker task.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


def _task_done_safe(queue: asyncio.Queue) -> None:
    """Call queue.task_done() without raising ValueError if called in excess."""
    try:
        queue.task_done()
    except ValueError:
        pass  # task_done() called more times than get() — safe to ignore


class TaskQueueManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.user_queues = {}  # user_id -> asyncio.Queue
            cls._instance.user_tasks  = {}  # user_id -> asyncio.Task (worker)
        return cls._instance

    async def add_task(self, user_id, target_chat_id, coro_func, *args, **kwargs):
        """Add a download task for a user; returns estimated queue position."""
        if user_id not in self.user_queues:
            self.user_queues[user_id] = asyncio.Queue()

        position = self.user_queues[user_id].qsize() + 1
        await self.user_queues[user_id].put({
            "target_chat_id": target_chat_id,
            "coro_func":      coro_func,
            "args":           args,
            "kwargs":         kwargs,
        })

        # Ensure a worker is running for this user
        worker = self.user_tasks.get(user_id)
        if worker is None or worker.done():
            self.user_tasks[user_id] = asyncio.create_task(self._worker(user_id))

        return position

    async def _worker(self, user_id):
        """Background worker — processes tasks for a user one at a time."""
        logger.info(f"Started task worker for user {user_id}")
        queue = self.user_queues[user_id]

        while True:
            # ── Peek: exit cleanly when queue is empty ─────────────────────
            if queue.empty():
                break

            # ── Dequeue ────────────────────────────────────────────────────
            task_dict = await queue.get()
            # From this point on we MUST call task_done() exactly once.

            try:
                import Plugins.helper as helper
                target_chat_id = task_dict["target_chat_id"]

                # Skip cancelled tasks but still mark done
                if helper.CANCEL_TASKS.get(target_chat_id, False):
                    logger.info(
                        f"Skipping cancelled task for chat {target_chat_id}"
                    )
                    continue  # finally below ensures task_done()

                coro_func = task_dict["coro_func"]
                args      = task_dict["args"]
                kwargs    = task_dict["kwargs"]

                await coro_func(*args, **kwargs)

            except Exception as e:
                logger.error(
                    f"Error executing queued task for user {user_id}: {e}",
                    exc_info=True,
                )
            finally:
                # Always call task_done() exactly once per get()
                _task_done_safe(queue)

        # Worker finished
        self.user_tasks.pop(user_id, None)
        logger.info(f"Finished task worker for user {user_id}")

    def clear_queue(self, target_chat_id):
        """
        Remove all pending tasks destined for target_chat_id.
        Calls task_done() for each removed item to keep the Queue's
        internal unfinished-task counter correct.
        """
        for user_id, queue in list(self.user_queues.items()):
            keep = []
            cleared = 0
            while not queue.empty():
                try:
                    item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if item["target_chat_id"] == target_chat_id:
                    # Mark done so the counter doesn't go negative later
                    _task_done_safe(queue)
                    cleared += 1
                else:
                    keep.append(item)

            # Re-queue the items we want to keep
            for item in keep:
                queue.put_nowait(item)

            if cleared > 0:
                logger.info(
                    f"Cleared {cleared} pending tasks for chat {target_chat_id}"
                )


task_manager = TaskQueueManager()
