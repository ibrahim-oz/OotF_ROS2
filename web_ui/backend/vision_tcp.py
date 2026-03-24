import asyncio
import logging

logger = logging.getLogger(__name__)

class VisionTCPClient:
    def __init__(self, host="192.168.137.110", port=50005):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.latest_data = ""

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            logger.info(f"Connected to Vision TCP Server at {self.host}:{self.port}")
            # Start a background task to listen for data
            asyncio.create_task(self._listen())
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Vision system: {e}")
            return False

    async def _listen(self):
        try:
            while self.reader:
                data = await self.reader.readline()
                if not data:
                    break
                decoded = data.decode('utf-8').strip()
                if decoded:
                    self.latest_data = decoded
                    logger.info(f"Received Vision string: {self.latest_data}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Vision listen error: {e}")
        finally:
            self.writer = None
            self.reader = None

    async def send_trigger(self, command="TRIGGER"):
        if not self.writer:
            connected = await self.connect()
            if not connected:
                return False, "Not connected"
                
        try:
            self.writer.write((command + "\r\n").encode())
            await self.writer.drain()
            return True, "Trigger sent"
        except Exception as e:
            self.writer = None
            self.reader = None
            return False, str(e)
