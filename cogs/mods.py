import discord
from discord.ext import commands, flags

class Moderation(commands.Cog):
    'Commands made by mods, for mods'
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(description='Kick someone out the server (they can still rejoin however)')
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        await ctx.guild.kick(member, reason=reason)
        await ctx.send(f'Kicked {member} out the server. Reason: {reason}')

    @commands.command(description='Kick multiple members out the server')
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def masskick(self, ctx, members: commands.Greedy[discord.Member], *, reason=None):
        'Use like so: p!ban @member @member2 @member3 reason for kick'
        if not members:
            return await ctx.send('I couldnt find anyone to kick')

        for member in members:
            await ctx.guild.kick(member, reason=reason)   

        await ctx.send(f'Kicked {len(members)} members. Reason: {reason}')

    @commands.command(cls=flags.FlagCommand, description='Ban someone from the server with an optional delete days number and an optional reason')
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @flags.add_flag('-days', type=int, default=1)
    @flags.add_flag('-reason', type=str, nargs='+')
    async def ban(self, ctx, member: discord.Member, **options):
        '''Use like so: p!ban @member -days 1-7 -reason reason for the ban
           
           The -days flag indicates how many days of messages to delete between 1 and 7 
           (defaults to 1)
           
           The -reason flag is for the reason 
           (shows up on audit log)'''
        
        if not 0 < options['days'] < 7:
            return await ctx.send('I cannot delete less than 0 days worth of messages, or greater than 7 days')
        
        reason = ' '.join(options['reason']) or None

        await ctx.guild.ban(member, reason=reason, delete_message_days=options['days'])
        await ctx.send(f'{member} has now been banned. Reason: {reason}')

    @commands.command(cls=flags.FlagCommand, description='Ban multiple members, useful for raiders. Optional delete days number and reason')
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @flags.add_flag('-days', type=int, default=1)
    @flags.add_flag('-reason', type=str, nargs='+')
    async def massban(self, ctx, members: commands.Greedy[discord.Member], **options):
        '''Use like so: p!massban @member1 @member2 @member3 -days 1-7 -reason reason given for ban
           As with the ban command, the -days flag indicates how many days worth of messages to delete and the -reason flag is for the audit log
           Use p!help ban for more info'''
        if not members:
            return await ctx.send('I couldnt find anyone to ban')
        
        if not 0 < options['days'] < 7:
            return await ctx.send('I cannot delete less than 0 days worth of messages, or more than 7 days')
        
        reason = ' '.join(options['reason']) or None

        for member in members:
            await ctx.guild.ban(member, reason=reason, delete_message_days=options['days'])  

        await ctx.send(f'Banned {len(members)} member(s). Reason: {reason}')

    @commands.command(description='Unban someone from the server by an ID or name#discrim')
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, member, *, reason=None):
        if member.isdigit():
            try:
                member = await ctx.guild.fetch_ban(discord.Object(member))
            except discord.NotFound:
                return await ctx.send('I couldnt find anyone by that ID')
        else:
            member = discord.utils.find(lambda m: str(m.user) == member, await ctx.guild.bans())
            if not member:
                return await ctx.send('I couldnt find anyone in the ban list by that name#discrim')
        
        await ctx.guild.unban(member.user, reason=reason)
        await ctx.send(f'Unbanned {member.user}. Reason: {reason}')

    @commands.group(invoke_without_command=True, description='The server mute role')
    @commands.has_permissions(manage_guild=True)
    async def muterole(self, ctx):
        role = await ctx.fetchrow(f'SELECT * FROM mod WHERE guild_id = {ctx.guild.id}')
        
        if not role:
            return await ctx.send('Your server has not set a mute role, so I will to default to the first role named Muted')
        
        role = ctx.guild.get_role(role['mute_role'])
        
        if not role:
            return await ctx.send(f'The mute role has not been found, please update this with {ctx.prefix}muterole set <role>')
        
        await ctx.send(f'The server mute role is: {role}')

    @muterole.command(name='set', description='Set a custom mute role')
    @commands.has_permissions(manage_guild=True)
    async def muterole_set(self, ctx, *, role: discord.Role):
        exists = await ctx.fetchrow(f'SELECT * FROM mod WHERE guild_id = {ctx.guild.id}')
        
        if exists:
            await ctx.execute(f"UPDATE mod SET guild_name = '{ctx.guild.name}', mute_role = {role.id} WHERE guild_id = {ctx.guild.id}")
            return await ctx.send(f'Changed the server mute role to {role}')
        
        await ctx.execute(f"INSERT INTO mod(guild_name, guild_id, mute_role) VALUES('{ctx.guild.name}', {ctx.guild.id}, {role.id})")
        await ctx.send(f'The new server mute role is now {role}')
    
    @commands.command(aliases=['silence'], description='Strip someone of all their roles and mute them')
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx, *, member: discord.Member):
        "The target's highest role must be lower than the bot's highest role"       
        if ctx.me.top_role < member.top_role:
            return await ctx.send(f'The {member.top_role} role is higher than my highest role, so I cannot remove their roles')
        
        mute_role = await ctx.fetchrow(f'SELECT * FROM mod WHERE guild_id = {ctx.guild.id}')
        
        if mute_role:
            mute_role = ctx.guild.get_role(mute_role['mute_role'])
            
            if not mute_role:
                return await ctx.send('Your server has most likely deleted the custom mute role, so I cannot continue')
        
        else:
            mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
            if not mute_role:
                return await ctx.send('Your server has not set a mute role yet, nor has a role named Muted')
        
        await member.remove_roles(*member.roles[1:], reason='Stripped roles for muted')        
        await member.add_roles(mute_role, reason=f'Muted by {ctx.author}')
        await ctx.send(f'Successfully muted {member.mention}')
    
    @commands.command(description="Remove someone's mute role")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx, *, member: discord.Member):
        mute_role = await ctx.fetchrow(f'SELECT * FROM mod WHERE guild_id = {ctx.guild.id}')
        
        if mute_role:
            mute_role = ctx.guild.get_role(mute_role['mute_role'])
            
            # deleting a mute role but still having another role called muted is an extremely rare case
            # but in the event, its better to be prepared
            if not mute_role:
                if not await ctx.prompt('Your server has deleted the custom mute role. Do you still want to remove any role called Muted?', ctx.author, timeout=60):
                    return await ctx.send('Cancelling mute role removal')

                roles_to_remove = [role for role in member.roles if role.name == 'Muted']
                if roles_to_remove:
                    return await member.remove_roles(*roles_to_remove, reason=f'Unmuted by {ctx.author}')
                else:
                    return await ctx.send('That person does not have any role named Muted')

        if mute_role not in member.roles:
            return await ctx.send('That person is not muted')
        
        await member.remove_roles(mute_role, reason=f'Unmuted by {ctx.author}') 
        await ctx.send(f'Successfully unmuted {member.mention}')

def setup(bot):
    bot.add_cog(Moderation(bot))