import discord
from discord.ext import commands

class Errors(commands.Cog):
    'Central error handler'
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        error = getattr(error, 'original', error)

        if ctx.cog and ctx.cog._get_overridden_method(ctx.cog.cog_command_error) or hasattr(ctx.command, 'on_error') or isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, (commands.BotMissingPermissions, discord.Forbidden)):
            return await ctx.send(f'I lack the permissions to continue the {ctx.command.name} command')

        if isinstance(error, commands.BotMissingRole):
            return await ctx.send(f'I do not have the role {error.missing_role} needed to continue')

        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(f'Sorry, but the {ctx.command} command is on cooldown for another {error.retry_after} seconds')

        if isinstance(error, commands.MaxConcurrencyReached):                                                 # strip away BucketType
            return await ctx.send(f'The {ctx.command} command can only be used by {error.number} people at a time on a {str(error.per)[11:]} basis')

        if isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'The {ctx.command.name} command is disabled for the time being')

        if isinstance(error, commands.NotOwner):
            return await ctx.send('This command can only be used by my owner')
        
        if isinstance(error, (commands.BadArgument, commands.MissingPermissions)):
            return await ctx.send(error) # no need to do anything special for bad arguments or missing permissions

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f'I seem to be missing the `{error.param.name}` input in {ctx.command.name}')
        
        if isinstance(error, commands.TooManyArguments):
            return await ctx.send(f'There are too many inputs provided for {ctx.command.name}')

        if isinstance(error, commands.ExtensionNotFound):
            return await ctx.send('I could not find an extension by that name')

        if isinstance(error, commands.ExtensionNotLoaded):
            return await ctx.send('It does not seem that extension is loaded')

        if isinstance(error, commands.ExtensionAlreadyLoaded):
            return await ctx.send('That extension is already loaded')

        await ctx.send(embed=discord.Embed(title='An error was raised:', color=0xffffff, description=f'{error.__class__.__name__}: {error}'))

def setup(bot):
    bot.add_cog(Errors(bot))