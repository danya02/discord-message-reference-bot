import os
import re
import asyncio

import discord
from discord.ext import commands

TOKEN = os.getenv('DISCORD_TOKEN')

client = commands.Bot(command_prefix=os.getenv('COMMAND_PREFIX') or '!', help_command=None)

DISCORD_LINK_REGEX = 'https:\/\/discord.com\/channels\/(\d+)\/(\d+)\/(\d+)'
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

def acquire_reference(match):
    guild, channel, message = map(int, match)
    return discord.MessageReference(message_id=message, channel_id=channel, guild_id=guild)

def get_jump_url(ref):
    if (discord.version_info.major == 1 and discord.version_info.minor >= 7) or (discord.version_info.major > 1): # check for version 1.7
        jump_url = ref.jump_url
    else:
        jump_url = f'https://discord.com/channels/{ref.guild_id}/{ref.channel_id}/{ref.message_id}'
    return jump_url

def get_error_embed(title, desc):
    embed = discord.Embed()
    embed.color = discord.Color.dark_red()
    embed.title = title
    embed.set_thumbnail(url='https://cdn.discordapp.com/app-assets/818957516129173575/818981523726139392.png')
    embed.description = desc
    return embed

async def send_reference(message, ref, index, count):
    # NOTE: as of 2021-03-10, Discord does not allow cross-channel replies.
    # Until this is implemented, an embed-based fallback is used for this.
    if (index, count) == (0,1): # if this is first and only reference, use special text
        text = f'{message.author.mention} referenced a message.'
    else:
        text = f'{message.author.mention} referenced multiple messages, this is #{index+1}/{count}.'

    try:
        await message.channel.send(content=text, reference=ref, mention_author=False)
    except discord.errors.HTTPException:
        resolved = ref.resolved
        channel = client.get_channel(ref.channel_id)
        if channel is None:
            jump_url = get_jump_url(ref)
            embed = get_error_embed('Channel unavailable',
                'This message was sent in a channel that this bot cannot access. Maybe I don\'t have enough permissions or this message is in a server I\'m not in. [Jump to Message]('+jump_url+')')
            embed.timestamp = discord.Object(ref.message_id).created_at
            embed.url = jump_url
            
            await message.channel.send(content=text, embed=embed)
            return

        try:
            resolved = await channel.fetch_message(ref.message_id)
        except discord.Forbidden:
            jump_url = get_jump_url(ref)
            embed = get_error_embed('Message unavailable',
                'This message cannot be accessed by this bot. Maybe I don\'t have enough permissions or this message is in a server I\'m not in. [Jump to Message]('+jump_url+')')
            embed.timestamp = discord.Object(ref.message_id).created_at
            embed.url = jump_url
            
            await message.channel.send(content=text, embed=embed)
            return
            
        embed = discord.Embed()
        if ref.message_id:
            embed.timestamp = discord.Object(ref.message_id).created_at
        embed.url = get_jump_url(ref)
        if isinstance(resolved, discord.DeletedReferencedMessage) or resolved is None:
            embed.color = discord.Color.red()
            embed.title='Unavailable message'
            embed.set_thumbnail(url='https://cdn.discordapp.com/app-assets/818957516129173575/818981523726139392.png')
            # The above URL is for the 1024x1024 PNG render of https://discord.com/assets/289673858e06dfa2e0e3a7ee610c3a30.svg, the Discord client's SVG for :warning: emoji. 
            # This is set as thumbnail because it is prominent in the embed.
            embed.description = 'This message could not be resolved at this time. This may mean that it has been deleted, or that the bot does not have the necessary permissions. [Jump to Message]('+embed.url+')'
        else:
            embed.color = discord.Color.random()
            embed.set_author(name=resolved.author.display_name, icon_url=resolved.author.avatar_url)
            embed.description = resolved.content
            if resolved.embeds:
                embed.add_field(name='Embed count', value=str(len(resolved.embeds)))
            if isinstance(resolved.channel, discord.TextChannel):
                embed.add_field(name='From channel', value=resolved.channel.mention)
            embed.add_field(name='From user', value=resolved.author.mention)
            for attach in resolved.attachments:
                if attach.width and attach.height:
                    embed.set_image(url=attach.proxy_url)
                    break
            if resolved.attachments:
                embed.add_field(name='Attachment count', value=str(len(resolved.attachments)))
        embed.description += ' [Jump to Message]('+embed.url+')'
        await message.channel.send(content=text, embed=embed)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    text = message.content
    matches = re.findall(DISCORD_LINK_REGEX, text)
    if len(matches) != 0:
        refs = [acquire_reference(match) for match in matches]
        for index, ref in enumerate(refs):
            await send_reference(message, ref, index, len(refs))
    await client.process_commands(message)


@client.command(name='ref', aliases=['link'])
async def get_link(ctx):
    if ctx.message.reference is None:
        await ctx.reply('You did not reference a message when you issued your command. Please retry with the "reply" feature of your Discord client.')
        return
    url = get_jump_url(ctx.message.reference)
    try:
        await ctx.message.delete()
        del_fail = False
    except:
        del_fail = True

    time_left = 60
    time_step = 10

    def get_text(time_left):
        text = f'{ctx.author.mention}, your mentioned message has this URL: {url}.'
        if del_fail:
            text += '\nThere was an error deleting the command message. Please check this bot\'s permissions.'
        text += f'\nThis message will be deleted in {time_left} seconds.'
        return text
    msg = await ctx.send(get_text(time_left))

    while time_left > 0:
        await asyncio.sleep(time_step)
        time_left -= time_step
        await msg.edit(content=get_text(time_left))
    await msg.delete()

client.run(TOKEN)
