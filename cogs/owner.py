import discord
from discord.ext import commands, tasks
import io
import textwrap
import os
import sys

class ExtensionConverter(commands.Converter):
    # converter to check if the extension is jsk
    async def convert(self, ctx, extension):
        if extension in ['jishaku', 'jsk']:
            return 'jishaku'
        return f'cogs.{extension}'

class Owner(commands.Cog):
    "Commands for yours truly"
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.group(invoke_without_command=True, description='Show those who have been blacklisted')
    async def blacklist(self, ctx):
        blacklist = await ctx.fetch('SELECT * FROM blacklist')
        if not blacklist or len(blacklist) == 0:
            return await ctx.send('There does not seem to be anyone blacklisted')
        res = ''
        for name, ids, reason in blacklist:
            res += f'{name} | {ids}   Reason: {reason}\n------------\n'
        await ctx.send(f'```{res}```')
    
    @blacklist.command(description='Add someone to the blacklist')
    async def add(self, ctx, members: commands.Greedy[discord.Member], *, reason='Not provided'):
        if not members:
            return await ctx.send('I need to know who to blacklist')

        for member in members:
            if await ctx.fetch(f'SELECT * FROM blacklist WHERE id = {member.id};'):
                return await ctx.send(f'{member} is already blacklisted')
            await ctx.execute(f"INSERT INTO blacklist(name, id, reason) VALUES('{member}', {member.id}, '{reason}');")
        
        await ctx.send(f"Added {', '.join(str(member) for member in members)} to the blacklist")
    
    @blacklist.command(description='Remove someone from the blacklist')
    async def remove(self, ctx, members: commands.Greedy[discord.Member]):
        if not members:
            return await ctx.send('I need to know who to unblacklist')

        for member in members:
            if not await ctx.fetch(f'SELECT * FROM blacklist WHERE id = {member.id};'):
                return await ctx.send(f'{member} is not blacklisted')
            await ctx.execute(f"DELETE FROM blacklist WHERE id = {member.id};")
        
        await ctx.send(f"Removed {', '.join(str(member) for member in members)} from the blacklist")

    @commands.command(aliases=['eval'], description='Evaluate Python code')
    async def evaluate(self, ctx, *, code):
        code = code.strip('```py\n').strip('```')
        env = {'bot': self.bot, 'ctx': ctx}
        
        try:
            exec(f'async def func():\n{textwrap.indent(code, "  ")}', env)
        except Exception as error:
            return await ctx.send(f'```py\n{error.__class__.__name__}: {error}```')
        
        try:
            ret = await env['func']()
        except Exception as error:
            return await ctx.send(f'```py\n{error.__class__.__name__}: {error}```')
        
        try:
            await ctx.message.add_reaction('✅')
        except:
            pass
        
    @commands.command(description='Load a given extension name')
    async def load(self, ctx, *, extension: ExtensionConverter):
        self.bot.load_extension(extension)
        await ctx.send(f'Loaded {extension}')
    
    @commands.command(description='Unload a given extension name')
    async def unload(self, ctx, *, extension: ExtensionConverter):
        self.bot.unload_extension(extension)
        await ctx.send(f'Unloaded {extension}')

    @commands.command(description='Reload a given extension name')
    async def reload(self, ctx, *, extension: ExtensionConverter = None):
        if not extension:
            for cog in os.listdir('./cogs'):
                if cog.endswith('.py'):
                    self.bot.reload_extension(f'cogs.{cog[:-3]}')
            self.bot.reload_extension('jishaku')
            return await ctx.send('Reloaded all extensions')
        self.bot.reload_extension(extension)
        await ctx.send(f'Reloaded {extension}')

    @commands.command(aliases=['reboot'], description='Restart the entire bot')
    async def restart(self, ctx):
        'Make sure to check your console for any errors'
        await ctx.send('Starting reboot process')
        await self.bot.close()
        os.system('clear')
        os.execv(sys.executable, ['python3.8'] + sys.argv)
        
def setup(bot):
    bot.add_cog(Owner(bot))