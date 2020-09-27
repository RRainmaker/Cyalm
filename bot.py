import discord
from discord.ext import commands
import config
import os
import datetime
from extras import Context

class Persona(commands.Bot):
    'A Discord bot created by Rainmaker dedicated to the video game series Persona'
    def __init__(self):
        super().__init__(command_prefix=self.prefix, description='A Discord bot based on the video game series Persona', case_insensitive=True)
        self.loop.create_task(self.create_tables())
        self.cooldown = commands.CooldownMapping.from_cooldown(7, 10, commands.BucketType.user)
        self.spam_strikes = {}
    
    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)
        
        if await self.is_owner(ctx.author):
            return await self.invoke(ctx)

        blacklist = []
        for member in await ctx.fetch('SELECT * FROM blacklist;'):
            blacklist.append(member['id'])

        if not message.content.startswith(tuple(await self.get_prefix(message))) or ctx.author.id in blacklist or ctx.author is self.user:
            return
        
        if self.cooldown.get_bucket(message).update_rate_limit(message.created_at.timestamp()):
            authorid = ctx.author.id
            if authorid not in self.spam_strikes.keys():
                self.spam_strikes[authorid] = 1
                return
            self.spam_strikes[authorid] += 1
            if self.spam_strikes[authorid] >= 5:
                del self.spam_strikes[authorid]
                await ctx.execute(f"INSERT INTO blacklist (name, id, reason) VALUES('{ctx.author}', {authorid}, 'Excessive command spamming');")
                return await ctx.send(f'{ctx.author.mention}, you are now blacklisted for excessive spamming')
                
        await self.invoke(ctx)
    
    async def on_ready(self):
        self.start_time = datetime.datetime.now()
        print(f'{self.user} is online and ready')
        await self.change_presence(activity=discord.Game('Persona 5 Royal (p!)'))

    async def prefix(self, bot, message):
        initial_prefixes = ['p!', 'persona!', 'P!']
        if message.guild:
            data = await Context.fetch(f'SELECT * FROM prefix WHERE guild_id = {message.guild.id}')
            if not data:
                pass
            else:
                data = data[0]
                if not data['no_default']:
                    initial_prefixes = data['prefixes'][::-1]
                elif data['prefixes']:
                    initial_prefixes.extend(data['prefixes'][::-1])
        
        return commands.when_mentioned_or(*initial_prefixes)(bot, message)

    async def on_guild_join(self, guild):
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return await channel.send(f'Hello, I am the Persona bot made by {self.get_user(self.owner_id)}. Thank you for having me, I hope we can build a great friendship')
                
    async def on_user_update(self, before, after):
        # this is to update the blacklist in case they change their name/discrim
        for member in await Context.fetch('SELECT * FROM blacklist;'):
            if before.id == member['id']:
                await Context.execute(f"UPDATE blacklist SET name = '{after}' WHERE id = {member['id']}")

    async def create_tables(self):
        # create postgres tables before anything
        await Context.execute('CREATE TABLE IF NOT EXISTS compendium(name text, id bigint, personas text [], level bigint, money bigint)')
        await Context.execute('CREATE TABLE IF NOT EXISTS blacklist(name text, id bigint, reason text)')
        await Context.execute('CREATE TABLE IF NOT EXISTS prefix(guild_name text, guild_id bigint, prefixes text [], no_default bool)')
        await Context.execute('CREATE TABLE IF NOT EXISTS mod(guild_name text, guild_id bigint, mute_role bigint)')

    def run(self):
        for cog in os.listdir('./cogs'):
            if cog.endswith('.py'):
                self.load_extension(f'cogs.{cog[:-3]}')
        self.load_extension('jishaku')
        super().run(config.bot_token)

    @property
    def config(self):
        return __import__('config')

Persona().run()