import discord
from discord.ext import commands, menus
import asyncio, async_timeout
import datetime, humanize, parsedatetime as parsedt
import math
import random
import wavelink
import re
from collections import deque

class Track(wavelink.Track):
    __slots__ = 'requester'
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.requester = kwargs.get('requester')

class Player(wavelink.Player):
    'Subclass of wavelink.Player with some extra functions'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = kwargs.get('ctx')
        self.dj = self.ctx.author
        self.queue = asyncio.Queue()
        self.controller = None
        self.updating = False
        self.pause_votes = self.resume_votes = self.skip_votes = self.shuffle_votes = self.stop_votes = set() # using set means every vote is unique 
        self.song_loop = {}
    
    async def next(self):
        if self.is_playing or self.updating:
            return
            
        self.pause_votes.clear()
        self.resume_votes.clear()
        self.skip_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()

        self.updating = True
        
        track = self.song_loop.get(self.guild_id)
        if not track:
            try:
                with async_timeout.timeout(300):
                    track = await self.queue.get()
            except asyncio.TimeoutError:
                return await self.teardown()
        
        await self.play(track)
        self.updating = False
        await self.start_controller()

    async def start_controller(self):
        self.updating = True

        embed = discord.Embed(title=f'<a:soundwaves:737809783867965521> Music Player @ {self.bot.get_channel(self.channel_id)}', color=self.ctx.pcolors, description=f'Now Playing:\n[**`{self.current.title}`**]({self.current.uri})')
        
        if self.current.thumb: 
            embed.set_thumbnail(url=self.current.thumb)
        
        embed.add_field(name='Song Progess', value=f"{str(datetime.timedelta(milliseconds=self.position)).split('.')[0]}/{str(datetime.timedelta(milliseconds=self.current.length)).split('.')[0]}")
        embed.add_field(name='Songs Queued', value=self.queue.qsize())
        embed.add_field(name='Volume', value=self.volume)
        embed.add_field(name='Requester', value=self.current.requester.mention)
        embed.add_field(name='DJ', value=self.dj.mention)
        
        if self.song_loop.get(self.guild_id):
            embed.add_field(name='Looping', value='Yes')
        else:
            embed.add_field(name='Looping', value='No')
        
        if not self.controller or not await self.ctx.channel.history(limit=5).find(lambda x: x.id == self.controller.message.id):
            try:
                await self.controller.message.delete()
            except (discord.HTTPException, AttributeError):
                pass
            self.controller = Controller(embed, self)
            await self.controller.start(self.ctx)

        else:    
            await self.controller.message.edit(embed=embed)

        self.updating = False
    
    async def teardown(self):
        try:
            await self.controller.message.delete()
        except (discord.HTTPException, AttributeError):
            pass
        try:
            await self.destroy()
        except KeyError:
            pass

class Controller(menus.Menu):
    'A subclass of menus.Menu for a music control panel'
    def __init__(self, embed, player):
        super().__init__(timeout=None)
        self.embed = embed
        self.player = player

    def reaction_check(self, payload):
        return payload.emoji in self._buttons and payload.event_type == 'REACTION_ADD' and payload.member and not payload.member.bot and payload.message_id == self.message.id and payload.member in self.bot.get_channel(self.player.channel_id).members

    async def send_initial_message(self, ctx, channel):
        return await ctx.send(embed=self.embed)

    @menus.button('⏸️')
    async def pause(self, payload):
        self.ctx.author = payload.member
        self.ctx.command = self.bot.get_command('pause')
        await self.bot.invoke(self.ctx)

    @menus.button('▶️')
    async def resume(self, payload):
        self.ctx.author = payload.member
        self.ctx.command = self.bot.get_command('resume')
        await self.bot.invoke(self.ctx)

    @menus.button('⏹️')
    async def stop(self, payload):
        self.ctx.author = payload.member
        self.ctx.command = self.bot.get_command('stop')
        await self.bot.invoke(self.ctx)

    @menus.button('⏩')
    async def skip(self, payload):
        self.ctx.author = payload.member
        self.ctx.command = self.bot.get_command('skip')
        await self.bot.invoke(self.ctx)

    @menus.button('🔀')
    async def shuffle(self, payload):
        self.ctx.author = payload.member
        self.ctx.command = self.bot.get_command('shuffle')
        await self.bot.invoke(self.ctx)

    @menus.button('🇶')
    async def queue(self, payload):
        self.ctx.author = payload.member
        self.ctx.command = self.bot.get_command('queue')
        await self.bot.invoke(self.ctx)

class Queue(menus.ListPageSource):
    "A subclass of menus.ListPageSource for the player's queue"
    def __init__(self, entries, ctx, *, per_page=10):
        super().__init__(entries, per_page=per_page)
        self.ctx = ctx

    async def format_page(self, menu, page):
        return discord.Embed(title='Queue', color=self.ctx.pcolors, description='\n'.join(f"{index}) [`{title}`]({title.uri})" for index, title in enumerate(page, (menu.current_page * self.per_page) + 1)))

    def is_paginating(self):
        return True

class QueuePages(menus.MenuPages):
    # this exists only for a reaction check, nothing else
    def __init__(self, source, **kwargs):
        super().__init__(source, **kwargs)
    
    def reaction_check(self, payload):
        return payload.emoji in self._buttons and payload.event_type == 'REACTION_ADD' and payload.member and not payload.member.bot and payload.message_id == self.message.id

class Music(commands.Cog, wavelink.WavelinkMixin):
    'Commands you can vibe to'
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(bot, 'wavelink'):
            bot.wavelink = wavelink.Client(bot=bot)
        bot.loop.create_task(self.startup())

    async def startup(self):
        if self.bot.wavelink.nodes:
            for node in self.bot.wavelink.nodes.copy().values():
                await node.destroy()
        
        await self.bot.wavelink.initiate_node(host=self.bot.config.wavehost, 
                                              port=self.bot.config.waveport, 
                                              rest_uri=f'http://{self.bot.config.wavehost}:{self.bot.config.waveport}', 
                                              password=self.bot.config.wavepass, 
                                              identifier='Persona', 
                                              region='us_east')
    
    async def cog_check(self, ctx):
        return ctx.guild

    async def cog_before_invoke(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)
        channel = self.bot.get_channel(player.channel_id)

        if ctx.command.name == 'connect' and not player.ctx or self.override(ctx) or not player.channel_id or not channel:
            return
        
        if player.is_connected and ctx.author not in channel.members or player.ctx and player.ctx.channel != ctx.channel:
            await ctx.send(f'Music commands are only usable in `{player.ctx.channel.name}` at the `{channel.name}` VC')
            raise commands.CheckFailure('') # raise an exception because return doesnt stop the command

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure) and not ctx.guild:
            # the only other error to raise check failure is no private messages
            return await ctx.send(f'The `{ctx.command.name}` command can only be used in a server and not a DM')

        await ctx.send(embed=discord.Embed(title='An error was raised:', color=0xffffff, description=f'{error.__class__.__name__}: {error}'))
    
    def cog_unload(self):
        self.bot.loop.create_task(self.startup())

    def votes(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)
        channel = self.bot.get_channel(player.channel_id)
        return 2 if ctx.command.name == 'stop' and len(channel.members) == 3 else math.ceil((len(channel.members) - 1) / 2)

    def override(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)
        return player.dj == ctx.author or ctx.author.guild_permissions.mute_members and ctx.author.guild_permissions.deafen_members

    @wavelink.WavelinkMixin.listener('on_track_stuck')
    @wavelink.WavelinkMixin.listener('on_track_exception')
    @wavelink.WavelinkMixin.listener('on_track_end')
    async def on_song_end(self, node, payload):
        await payload.player.next()

    @commands.command(aliases=['join'], description='Connect to a voice channel')
    async def connect(self, ctx, *, channel: discord.VoiceChannel = None):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if self.override(ctx):
            pass

        elif player.is_connected and player.is_playing: 
            return await ctx.send('I am already playing music in another channel')

        channel = getattr(ctx.author.voice, 'channel', channel)
        
        if not channel: 
            # return False for the play command
            return not await ctx.send('There does not seem to be a channel provided for me to join')

        await player.connect(channel.id)
        return await ctx.send(f'Joined to {channel.name}')
    
    @commands.command(aliases=['p', 'scplay', 'soundcloudplay'], description='Play a song of your choice. Use scplay to load SoundCloud songs')
    async def play(self, ctx, *, query):
        query = query.strip('<>')
        
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)
            
        if not player.is_connected and not await ctx.invoke(self.connect):
            return

        if re.match(r'https?://(?:www\.)?.+', query):
            tracks = await self.bot.wavelink.get_tracks(query)

        elif ctx.invoked_with in ['scplay', 'soundcloudplay']:
            tracks = await self.bot.wavelink.get_tracks(f'scsearch:{query}')
        
        else:
            tracks = await self.bot.wavelink.get_tracks(f'ytsearch:{query}')
        
        if not tracks:    
            return await ctx.send('No songs were found with the provided query')

        if isinstance(tracks, wavelink.TrackPlaylist):
            for track in tracks.tracks:
                await player.queue.put(Track(track.id, track.info, requester=ctx.author))
            await ctx.send(f'Added {len(tracks.tracks)} songs in the `{tracks.data["playlistInfo"]["name"]}` playlist')
        
        else:
            await player.queue.put(Track(tracks[0].id, tracks[0].info, requester=ctx.author))
            await ctx.send(f'Added `{tracks[0].title}`')

        if not player.is_playing:
            await player.next()

    @commands.command(description='Pause the current song')
    async def pause(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if player.is_paused or not player.is_connected:
            return await ctx.send('There is no song currently playing')

        if self.override(ctx):
            await ctx.send('A higher power has forcibly paused the player')
            player.pause_votes.clear()
            return await player.set_pause(True)

        player.pause_votes.add(ctx.author)

        if len(player.pause_votes) >= self.votes(ctx):
            await ctx.send('Sufficient votes to pause reached')
            player.pause_votes.clear()
            return await player.set_pause(True)

        await ctx.send(f'{ctx.author.mention} has voted to pause the player, {len(player.pause_votes) - self.votes(ctx)} votes left')

    @commands.command(description='Resume the current song')
    async def resume(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected:
            return await ctx.send('I am not connected to a channel')
        
        if not player.is_playing:
            return await ctx.send('Theres no song playing')

        if not player.is_paused:
            return await ctx.send('There is already a song currently playing')

        if self.override(ctx):
            await ctx.send('A higher power has forcibly resumed the player')
            player.resume_votes.clear()
            return await player.set_pause(False)

        player.resume_votes.add(ctx.author)

        if len(player.resume_votes) >= self.votes(ctx):
            await ctx.send('Sufficient votes to resume reached')
            player.resume_votes.clear()
            return await player.set_pause(False)

        await ctx.send(f'{ctx.author.mention} has voted to resume the player, {len(player.resume_votes) - self.votes(ctx)} votes left')

    @commands.command(description='Skip to the next song. This also stops any songs being looped')
    async def skip(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected: 
            return await ctx.send('I am not connected to a channel')
        
        if self.override(ctx):
            await ctx.send('A higher power has forcibly skipped the song')
            player.skip_votes.clear()
            try:
                del player.song_loop[ctx.guild.id]
            except KeyError:
                pass
            return await player.stop()

        player.skip_votes.add(ctx.author)

        if len(player.skip_votes) >= self.votes(ctx):
            await ctx.send('Sufficient votes to skip reached')
            player.skip_votes.clear()
            try:
                del player.song_loop[ctx.guild.id]
            except KeyError:
                pass
            return await player.stop()

        await ctx.send(f'{ctx.author.mention} has voted to skip the song, {len(player.skip_votes) - self.votes(ctx)} votes left')

    @commands.command(aliases=['dc', 'disconnect'], description='Stop the entire player')
    async def stop(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected:
            return await ctx.send('No song is currently playing')

        if self.override(ctx):
            await ctx.send('A higher power has forcibly stopped the player')
            player.stop_votes.clear()
            try:
                del player.song_loop[ctx.guild.id]
            except KeyError:
                pass
            return await player.teardown()

        player.stop_votes.add(ctx.author)

        if len(player.stop_votes) >= self.votes(ctx):
            await ctx.send('Sufficient votes to stop reached')
            player.stop_votes.clear()
            try:
                del player.song_loop[ctx.guild.id]
            except KeyError:
                pass
            return await player.teardown()
        
        await ctx.send(f'{ctx.author.mention} has voted to stop the player, {len(player.stop_votes) - self.votes(ctx)} votes left')

    @commands.command(aliases=['v', 'vol'], description='Change the volume of the song')
    async def volume(self, ctx, *, volume: int):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected or not player.is_playing: 
            return await ctx.send('Currently, no song is playing')

        if not self.override(ctx):
            return await ctx.send('Only the DJ or admins may change the volume')

        if not 0 < volume < 101:
            return await ctx.send('The minimum volume is 1 and the maximum is 100')

        await player.set_volume(volume)
        await ctx.send(f'Set the volume to {volume}')

    @commands.command(description='Shuffle all of the queued songs')
    async def shuffle(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected:
            return await ctx.send('I am not connected to a channel')

        if player.queue.qsize() < 3:
            return await ctx.send('I need at least 3 queued songs in order to shuffle')

        if self.override(ctx):
            await ctx.send('A higher power has forcibly shuffled the playlist')
            player.shuffle_votes.clear()
            return random.shuffle(player.queue._queue)

        player.shuffle_votes.add(ctx.author)

        if len(player.shuffle_votes) >= self.votes(ctx):
            await ctx.send('Sufficient votes to shuffle reached')
            player.shuffle_votes.clear()
            return random.shuffle(player.queue._queue)

        await ctx.send(f'{ctx.author.mention} has voted to shuffle the playlist')

    @commands.command(aliases=['eq'], description='Change the equalizer')
    async def equalizer(self, ctx, *, equalizer):
        '''There are 4 base equalizers avaliable: 
           flat to reset equalizers,
           boost,
           metal,
           and piano'''
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected or not player.is_playing: 
            return await ctx.send('Currently, no song is playing')

        if not self.override(ctx): 
            return await ctx.send('Only the DJ or people with mute & deaf permissions may change the equalizer')

        eqs = {'flat': wavelink.Equalizer.flat(), 
               'boost': wavelink.Equalizer.boost(), 
               'metal': wavelink.Equalizer.metal(), 
               'piano': wavelink.Equalizer.piano()}

        keys = eqs.keys()
        eq = equalizer.lower()

        if eq not in keys: 
            return await ctx.send(f'I could not find that equalizer from these {len(keys)}:\n' + '\n'.join(keys))

        await player.set_eq(eqs[eq])
        await ctx.send(f'Successfully changed equalizer to {eq}')

    @commands.command(aliases=['q'], description='View the songs queued')
    async def queue(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected: 
            return await ctx.send('I am not connected to a channel')

        if player.queue.qsize() == 0: 
            return await ctx.send('There are no more songs in the queue')

        await QueuePages(Queue(list(player.queue._queue), ctx), timeout=None, delete_message_after=True).start(ctx)
    
    @commands.command(aliases=['np', 'current'], description='Shows the song currently playing alongside a music controller')
    async def nowplaying(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected or not player.is_playing: 
            return await ctx.send('Currently, no song is playing')

        await player.start_controller()
    
    @commands.command(description='Loop the current song')
    async def loop(self, ctx):
        player: Player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected or not player.is_playing: 
            return await ctx.send('Currently, no song is playing')

        if not self.override(ctx): 
            return await ctx.send('Only the DJ or people with mute & deaf permissions may loop')
        
        track = player.song_loop.get(ctx.guild.id)
        
        if track:
            del player.song_loop[ctx.guild.id]
            await ctx.send('Disabled song loop')
        
        else:
            player.song_loop[ctx.guild.id] = player.current
            await ctx.send('Enabled song looping')
        
        await player.start_controller()       

    @commands.command(description='Seek to a certain point in the song')
    async def seek(self, ctx, *, position):
        '''Examples:
           `seek 5 minutes`
           `seek seven minutes and three seconds`'''
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)
        
        if not player.is_connected or not player.is_playing: 
            return await ctx.send('Currently, no song is playing')
        
        if not self.override(ctx): 
            return await ctx.send('Only the DJ or people with mute & deaf permissions may seek')
        
        offset = parsedt.Calendar().parseDT(position)[0] - datetime.datetime.now() # find the offset of the specified time since there isnt a function for that
        time = math.ceil(abs(offset.total_seconds()))
        await player.seek(time * 1000) # convert to milliseconds 
        await ctx.send(f'Seeked to {humanize.naturaldelta(datetime.timedelta(seconds=time))} in the song')

    @commands.command(aliases=['switchdj'], description='Swap the DJ to someone else')
    async def swapdj(self, ctx, *, member: discord.Member):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, ctx=ctx)

        if not player.is_connected: 
            return await ctx.send('I am not connected to a channel')
        
        if not self.override(ctx): 
            return await ctx.send('Only the DJ or people with mute & deaf permissions may change the DJ')

        if member not in self.bot.get_channel(player.channel_id).members: 
            return await ctx.send(f'{member} is currently not in voice, and thus cannot be a DJ')

        if member == player.dj: 
            return await ctx.send('That person is already the DJ')

        if len(self.bot.get_channel(player.channel_id).members) <= 2: 
            return await ctx.send('No more members to swap to')

        if member.bot:
            return await ctx.send('You cannot make a bot the DJ')

        player.dj = member
        await ctx.send(f'{member.mention} is now the DJ')

def setup(bot):
    bot.add_cog(Music(bot))
