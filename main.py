import os
import re

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

client = discord.Client()

DISCORD_LINK_REGEX = 'https:\/\/discord.com\/channels\/(\d+)\/(\d+)\/(\d+)'
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

def acquire_reference(match):
    guild, channel, message = map(int, match)
    return discord.MessageReference(message_id=message, channel_id=channel, guild_id=guild)

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
            if (discord.version_info.major == 1 and discord.version_info.minor >= 7) or (discord.version_info.major > 1): # check for version 1.7
                jump_url = ref.jump_url
            else:
                jump_url = f'https://discord.com/channels/{ref.guild_id}/{ref.channel_id}/{ref.message_id}'
            embed = discord.Embed()
            embed.color = discord.Color.dark_red()
            embed.set_author(name='Unavailable channel', icon_url='https://cdn.discordapp.com/app-assets/818957516129173575/818981523726139392.png')
            embed.description = 'This message was sent in a channel that this bot cannot access. Perhaps it doesn\'t have the proper permissions or the message is in a server that this bot is not a part of.  [Jump to Message]('+jump_url+')'
            embed.url = jump_url
            embed.timestamp = discord.Object(ref.message_id).created_at
            
            await message.channel.send(content=text, embed=embed)
            return


        resolved = await channel.fetch_message(ref.message_id)
        embed = discord.Embed()
        if ref.message_id:
            embed.timestamp = discord.Object(ref.message_id).created_at
        if (discord.version_info.major == 1 and discord.version_info.minor >= 7) or (discord.version_info.major > 1): # check for version 1.7
            jump_url = ref.jump_url
        else:
            jump_url = f'https://discord.com/channels/{ref.guild_id}/{ref.channel_id}/{ref.message_id}'
        embed.url = jump_url
        if isinstance(resolved, discord.DeletedReferencedMessage) or resolved is None:
            embed.color = discord.Color.red()
            embed.set_author(name='Unavailable message', icon_url='https://cdn.discordapp.com/app-assets/818957516129173575/818981523726139392.png')
            # The above URL is for the 1024x1024 PNG render of https://discord.com/assets/289673858e06dfa2e0e3a7ee610c3a30.svg, the Discord client's SVG for :warning: emoji. 
            # This is set as author because it is displayed at top of embed.
            embed.description = 'This message could not be resolved at this time. This may mean that it has been deleted, or that the bot does not have the necessary permissions.'
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
        embed.description += ' [Jump to Message]('+jump_url+')'
        await message.channel.send(content=text, embed=embed)

@client.event
async def on_message(message):
    text = message.content
    matches = re.findall(DISCORD_LINK_REGEX, text)
    if len(matches) == 0: return
    refs = [acquire_reference(match) for match in matches]
    for index, ref in enumerate(refs):
        await send_reference(message, ref, index, len(refs))


client.run(TOKEN)
