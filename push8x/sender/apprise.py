import apprise
from loguru import logger

from ..constans import Msg, MsgContentType, SenderType
from ..worker import worker_guardian
from .common import SenderAbc


class SenderApprise(SenderAbc):

    @property
    def type(self) -> SenderType:
        return SenderType.APPRISE

    def _do_task(self, msg: Msg):
        ap = apprise.Apprise()
        ap.add(msg.to_value)
        match msg.content_format:
            case MsgContentType.PLAIN:
                body_format = apprise.NotifyFormat.TEXT
            case MsgContentType.HTML:
                body_format = apprise.NotifyFormat.HTML
            case MsgContentType.MARKDOWN:
                body_format = apprise.NotifyFormat.MARKDOWN
        ap.notify(body=msg.content, title=msg.title, body_format=body_format)

    @worker_guardian()
    async def worker(self):
        while True:
            msg = await self.q.get()
            logger.debug(f"got Msg: {msg}")
            self._do_task(msg)
