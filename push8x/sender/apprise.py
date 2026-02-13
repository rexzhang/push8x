from logging import getLogger

import apprise

from ..constans import Msg, MsgContentType
from .common import SenderAbc

logger = getLogger(__name__)


class SenderApprise(SenderAbc):
    def _do_task(self, msg: Msg):
        ap = apprise.Apprise()
        ap.add(msg.t_value)
        match msg.content_format:
            case MsgContentType.PLAIN:
                body_format = apprise.NotifyFormat.TEXT
            case MsgContentType.HTML:
                body_format = apprise.NotifyFormat.HTML
            case MsgContentType.MARKDOWN:
                body_format = apprise.NotifyFormat.MARKDOWN
        ap.notify(body=msg.content, title=msg.title, body_format=body_format)

    async def worker(self):
        while True:
            msg = await self.q.get()
            logger.debug(f"got Msg: {msg}")
            self._do_task(msg)
