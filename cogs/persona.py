import discord
from discord.ext import commands
import wikia
from extras import personas
import random
import functools

class Persona(commands.Cog):
    "Commands related to Persona"
    def __init__(self, bot):
        self.bot = bot

    @commands.command(description='Check your profile or others profiles')
    async def profile(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author
        data = await ctx.fetch(f"SELECT * FROM compendium WHERE id = {member.id};", type='row')
        
        if not data:
            return await ctx.send(f'It seems {member} has no data')
        
        embed = discord.Embed(title=f"{member.name}'s profile")
        embed.set_thumbnail(url=member.avatar_url)
        embed.add_field(name='Money', value=f"¥{data['money']}")
        embed.add_field(name='Highest Level Persona', value=max(data['persona']))
        embed.add_field(name='Level', value=data['level'])
        
        await ctx.send(embed=embed)

    @commands.command(description='See your Personas or the Personas of others')
    async def personas(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author
        data = await ctx.fetch(f"SELECT * FROM compendium WHERE id = {member.id};", type='row')
        
        if not data:
            return await ctx.send(f'It seems {member} does not have any Personas')
        
        await ctx.send(f"{member.name}'s Personas: ```" + '\n'.join(data['persona']) + '```')

    @commands.command(aliases=['persona_info'], description='Get info about anything from the Persona wiki')
    async def personainfo(self, ctx, *, persona):
        def wiki_finder(query):
            page = wikia.page('megamitensei', query)
            if 'REDIRECT' in page.summary:
                page = wikia.page('megamitensei', page.summary[9:])

            embed = discord.Embed(title=page.title, description=page.summary, url=page.url.replace(' ', '_'))
            if page.images:
                embed.set_thumbnail(url=page.images[0])
            return embed
        
        persona = ' '.join([word.capitalize() for word in persona.split(' ')])
        await ctx.send(embed=await self.bot.loop.run_in_executor(None, functools.partial(wiki_finder, persona)))

    @commands.command(description='Get a random Persona', enabled=False)
    async def unpack(self, ctx):
        data = await ctx.fetch(f"SELECT * FROM compendium WHERE id = {ctx.author.id};", type='row')

        if data:
            level = data['level']
        else:
            level = 1

        reward = list(random.choice(list(personas.items())))

        # this iterates until the persona is equal or lower than the person's current level
        while level <= reward[0]:
            reward = list(random.choice(list(personas.items())))
        
        if data:
            await ctx.execute(f"UPDATE compendium SET persona = array_append(ARRAY{data['persona']}, 'Lv. {reward[0]} {reward[1]}') WHERE id = {ctx.author.id}")
        else:
            await ctx.execute(f'''INSERT INTO compendium(name, id, persona, level, money) VALUES('{ctx.author.name}', {ctx.author.id}, ARRAY['Lv. {reward[0]} {reward[1]}'], {level}, 100)''')
        
        await ctx.send(f'The Lv. {reward[0]} Persona {reward[1]} has entered your heart')

def setup(bot):
    bot.add_cog(Persona(bot))