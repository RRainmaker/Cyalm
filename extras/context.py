import discord
from discord.ext import commands, menus
import asyncpg
import config
import random

class Confirmation(menus.Menu):
    def __init__(self, content, recipient, timeout):
        super().__init__(timeout=timeout)
        self._author_id = recipient.id
        self.content = content

    async def send_initial_message(self, ctx, channel):
        return await ctx.send(self.content)

    @menus.button('✅')
    async def confirm(self, payload):
        self.result = True
        self.stop()
    
    @menus.button('❌')
    async def deny(self, payload):
        self.result = False
        self.stop()
    
    async def begin(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

class Context(commands.Context):
    'A commands.Context subclass to store extra functions'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # SQL functions

    @classmethod
    async def fetch(cls, query, *args):
        async with asyncpg.create_pool(config.postgres) as pool:
            try:
                return await pool.fetch(query, *args)
            finally:
                await pool.close()

    @classmethod
    async def execute(cls, query, *args):
        async with asyncpg.create_pool(config.postgres) as pool:
            try:
                return await pool.execute(query, *args)
            finally:
                await pool.close()
    
    async def prompt(self, content, recipient: discord.Member, timeout: int):
        return await Confirmation(content, recipient, timeout).begin(self)
    
    @property
    def pcolors(self):
        'A property to randomly return blue, yellow and red, the theme colors of Persona 3/4/5'
        return random.choice([0xff0000, 0x0000ff, 0xffff00])
