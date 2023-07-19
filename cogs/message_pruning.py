"""Delete old messages in a channel."""

import asyncio
import collections.abc
import datetime
import logging
import os

import discord
import dotenv

from discord.ext import commands
from discord.ext import tasks

import conf
from cogs import base_cog

logger = logging.getLogger(__name__)


class MessagePruning(base_cog.BaseCog):
    """Prune old messages."""

    qualified_name = "Message Pruning"

    def __init__(
        self,
        bot: commands.Bot,
        channel_ids: dict[int, collections.abc.Sequence[int]],
        **kwargs,
    ) -> None:
        """Initialize the cog."""
        super().__init__(bot=bot, **kwargs)
        self.channel_ids = channel_ids
        self.task_prune_old_messages.start()

    @tasks.loop(hours=4)
    async def task_prune_old_messages(self) -> None:
        """Delete old messages."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        before = now - datetime.timedelta(days=7)

        for guild_id, channel_ids in self.channel_ids.items():
            guild = self.bot.get_guild(guild_id)
            member = guild.me
            for channel_id in channel_ids:
                count = 0
                channel = self.bot.get_channel(channel_id)
                if not channel.permissions_for(member).read_message_history:
                    logger.warning("Skip %s; not able to read_message_history.", channel.name)
                    continue
                if not channel.permissions_for(member).manage_messages:
                    logger.warning("Skip %s; not able to manage messages.", channel.name)
                    continue
                logger.warning("Starting message purge of %s.", channel.name)
                try:
                    await anext(channel.history(limit=1, before=before))
                except StopAsyncIteration as exception:
                    logger.warning("Nothing to purge in %s: %s.", channel.name, str(exception))
                    continue
                async for message in channel.history(limit=None, oldest_first=True, before=before):
                    assert message.created_at <= before
                    await message.delete()
                    await asyncio.sleep(1)
                    count += 1
                logger.warning("Deleted %d msgs from %s.", count, channel.name)

    @task_prune_old_messages.before_loop
    async def before_prune_old_messages(self) -> None:
        """Wait until ready before starting to prune."""
        await self.bot.wait_until_ready()

    async def cog_unload(self) -> None:
        """Stop the task on unload."""
        self.task_prune_old_messages.cancel()


class Bot(commands.Bot):
    """Simple bot to load and run the cog."""

    async def setup_hook(self) -> None:
        """Add the cog on setup."""
        await self.add_cog(MessagePruning(self, conf.CHANNELS_TO_PRUNE))


def main() -> None:
    """Run a bot with the cog."""
    dotenv.load_dotenv()
    intents = discord.Intents.default()
    Bot(command_prefix="=", intents=intents).run(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    main()
