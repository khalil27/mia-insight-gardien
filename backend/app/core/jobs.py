"""
In-memory job registry for SSE streaming.
Each job has an asyncio.Queue fed by the pipeline background task
and drained by the /evaluate/{job_id}/stream SSE endpoint.
"""
import asyncio
import uuid
from typing import Any, Dict, Optional


class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.done: bool = False

    async def push(self, event: dict) -> None:
        await self.queue.put(event)

    async def finish(self, result: dict) -> None:
        self.done = True
        await self.queue.put({"step": "done", "result": result})
        await self.queue.put(None)  # sentinel

    async def fail(self, message: str) -> None:
        self.done = True
        await self.queue.put({"step": "error", "message": message})
        await self.queue.put(None)

    async def event_stream(self):
        """Async generator: yields events until sentinel None."""
        while True:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=60)
            except asyncio.TimeoutError:
                yield {"step": "ping"}
                continue
            if event is None:
                break
            yield event


_registry: Dict[str, Job] = {}


def create_job() -> Job:
    job = Job(str(uuid.uuid4()))
    _registry[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _registry.get(job_id)
