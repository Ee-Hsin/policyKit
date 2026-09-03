"""Run the durable compliance worker as a separate process."""

import asyncio

from app.agent.worker import AgentWorker
from app.core.config import get_settings


def main() -> None:
    try:
        asyncio.run(AgentWorker(get_settings()).run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
