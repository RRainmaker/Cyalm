import discord
from discord.ext import commands
import math
import random

class Fun(commands.Cog):
    'Commands made for fun'
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True, description='Get a random quote from a user')
    @commands.guild_only()
    async def quote(self, ctx, *, member: discord.Member = None):
        guild_data = await ctx.fetchrow(f'SELECT * FROM quotes WHERE guild_id = {ctx.guild.id}')
        
        if not guild_data or not guild_data['quoted_members']:
            return await ctx.send(f'I dont have any quotes stored. Use {ctx.prefix}help quote add to see how to add a quote')
            
        if not member:
            member = random.choice(guild_data['quoted_members'])
            quote = random.choice(member[2:])
            return await ctx.send(f'Here is a quote from {member[0]}:\n> {quote}')
            
        quote = discord.utils.find(lambda m: m[1] == str(member.id), guild_data['quoted_members'])

        if not quote:
            return await ctx.send('I couldnt find a quote for that member')

        await ctx.send(f'Heres a quote from {quote[0]}:\n> {random.choice(quote[2:])}')

    @quote.command(description='Add a quote to someone')
    @commands.check_any(commands.is_owner(), commands.has_guild_permissions(manage_guild=True))
    async def add(self, ctx, member: discord.Member, *, quote):
        guild_data = await ctx.fetchrow(f'SELECT * FROM quotes WHERE guild_id = {ctx.guild.id}')

        if not guild_data or not guild_data['quoted_members']:
            await ctx.execute(f"INSERT INTO quotes(guild_name, guild_id, quoted_members) VALUES('{ctx.guild.name}', {ctx.guild.id}, ARRAY[['{member}', '{member.id}', '{quote}']])")
        
        elif guild_data['quoted_members']:
            guild_data['quoted_members'].append([str(member), str(member.id), quote])
            await ctx.execute(f"UPDATE quotes SET quoted_members = ARRAY{guild_data['quoted_members']} WHERE guild_id = {ctx.guild.id}")

        await ctx.send(f'Added the quote "{quote}" to {member}')

    @quote.command(description='Remove a quote from someone')
    @commands.check_any(commands.is_owner(), commands.has_guild_permissions(manage_guild=True))
    async def remove(self, ctx, member: discord.Member, *, quote):
        guild_data = await ctx.fetchrow(f'SELECT * FROM quotes WHERE guild_id = {ctx.guild.id}')

        if not guild_data or not guild_data['quoted_members']:
            return await ctx.send('Your server doesnt have any quotes set')

        if not discord.utils.find(lambda m: m[1] == str(member.id), guild_data['quoted_members']):
            return await ctx.send('That person doesnt have any quotes to remove')
        
        if not discord.utils.find(lambda m: m[1] == str(member.id) and quote in m, guild_data['quoted_members']):
            return await ctx.send('That person doesnt have that quote')

        for elem in guild_data['quoted_members']:
            if elem[1] == str(member.id) and quote in elem:
                guild_data['quoted_members'].remove(elem)
                await ctx.execute(f"UPDATE quotes SET quoted_members = ARRAY{guild_data['quoted_members']}::text[] WHERE guild_id = {ctx.guild.id}")
                return await ctx.send(f'Removed "{quote}" from {member}')
    
    @quote.command(description='Splice two random quotes together')
    @commands.guild_only()
    async def splice(self, ctx, members: commands.Greedy[discord.Member]):
        guild_data = await ctx.fetchrow(f'SELECT * FROM quotes WHERE guild_id = {ctx.guild.id}')

        if not guild_data or not guild_data['quoted_members']:
            return await ctx.send('Your server doesnt have any quotes set')
        
        if len(guild_data['quoted_members']) <= 1:
            return await ctx.send('I dont have enough quotes to splice')

        if members:
            if len(members) == 1:
                return await ctx.send('I need at least two people to splice quotes from\nAlternitively, you can run the command without specifying two people')
            
            if not discord.utils.find(lambda m: m[1] == str(members[0].id), guild_data['quoted_members']):
                return await ctx.send(f'{members[0]} doesnt have a quote stored')
            
            if not discord.utils.find(lambda m: m[1] == str(members[1].id), guild_data['quoted_members']):
                return await ctx.send(f'{members[1]}  doesnt have a quote stored')
            
            member1 = members[0]
            member2 = members[1]
            
            quote1 = random.choice([m for m in guild_data['quoted_members'] if m[1] == str(member1.id)])
            quote2 = random.choice([m for m in guild_data['quoted_members'] if m[1] == str(member2.id)])

        else:
            quote1 = random.choice(guild_data['quoted_members'])
            member1 = quote1[0]
            
            quote2 = random.choice(guild_data['quoted_members'])

            while quote1[1] == quote2[1]:
                quote2 = random.choice(guild_data['quoted_members'])

            member2 = quote2[0]

        quote1 = quote1[2].split(' ')
        decoy1 = ' '.join(quote1[math.ceil(len(quote1) / 2):])
        decoy2 = ' '.join(quote1[:math.ceil(len(quote1) / 2)])
        quote1 = random.choice([decoy1, decoy2])
        
        quote2 = quote2[2].split(' ')
        decoy1 = ' '.join(quote2[math.ceil(len(quote2) / 2):])
        decoy2 = ' '.join(quote2[:math.ceil(len(quote2) / 2)])
        quote2 = random.choice([decoy1, decoy2])

        await ctx.send(f"Combined quotes from {member1} and {member2}\n> {quote1 + ' ' + quote2}")


def setup(bot):
    bot.add_cog(Fun(bot))