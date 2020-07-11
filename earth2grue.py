import os, asyncio
import unicodedata
from twitchio.ext import commands
import discord
from dotenv import load_dotenv
load_dotenv()
import socket, json, sys
from collections import defaultdict

if len(sys.argv) != 3:
    sys.exit(sys.argv[0] + ' MODE PORT')

mode_arg, port_arg = sys.argv[1:]

GUILD = os.environ['DISCORD_GUILD']

translate_emojis = {
    '🔄':'bassin',
    '↕':'epaule',
    '↪':'coude',
    '↔':'pince',
}

last_position = defaultdict(lambda : 10)

for key, value in list(translate_emojis.items()):
    byte_key = bytes(key, 'utf-8')
    print(key)
    if byte_key[-3:] == b'\xef\xb8\x8f':
        translate_emojis[key[:-1]] = value

twitch = commands.Bot(
    # set up the bot
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=[os.environ['CHANNEL']]
)

discord_bot = discord.Client()

def init_socket():
    global sock
    print("Creating socket")
    sock = socket.socket()
    print("Opening port")
    host = os.environ['EV3HOST']
    port = int(port_arg)
    print("Waiting for connection...")
    sock.connect((host, port))
    print("Connected")

def receive():
    global sock
    buffer = sock.recv(4096)
    try:
        return json.loads(buffer.decode())
    except ValueError:
        raise ValueError("Impossible to decode '" + buffer.decode() + "'")

def send(data):
    global sock
    sock.send(json.dumps(data).encode())

class dummy_channel(object):
    async def send(self, message):
        print('robot:"' + message + '"')

class dummy_context(object):
    def __init__(self, message):
        self.channel = dummy_channel()
        self.content = message

async def interpret_ctx(ctx):
    if not ctx.content.startswith('robot'):
        return
    send(ctx.content[0:4000])
    feedback = receive()
    print(feedback)
    await ctx.channel.send(str(feedback))


def decode_emojis(string):
    string = unicodedata.normalize('NFC', string)
    ret = []
    integral = 0
    for each in string:
        if each in translate_emojis:
            ret.append((min(integral, 100) if integral else 1, translate_emojis[each]))
            integral = 0
        else:
            try:
                integral = integral * 10 + int(each)
            except ValueError:
                integral = 0
    return ret


async def interpret_ctx_emoji(ctx):
    instructions = decode_emojis(ctx.content)
    print(f'instructions "{instructions}"')
    if instructions:
        for position, motor in instructions:
            last_position[motor] = position
        send(instructions)
        feedback = receive()
        print(feedback)
        await ctx.channel.send(str(feedback))
    if 'robot' in ctx.content or instructions:
        for code, motor in translate_emojis.items():
            await ctx.channel.send(f'{code} : {motor} ({last_position[motor]})')


@twitch.event
async def event_ready():
    'Called once when the bot goes online.'
    print(f"{os.environ['BOT_NICK']} est connecté!")
    ws = twitch._ws  # this is only needed to send messages within event_ready
    await ws.send_privmsg(os.environ['CHANNEL'], f"/me est connecté")

@twitch.event
async def event_message(ctx):
    'Runs every time a message is sent in chat.'

    # make sure the bot ignores itself and the streamer
    if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():
        return

    await interpret_ctx_emoji(ctx)

@discord_bot.event
async def on_ready():
    for guild in discord_bot.guilds:
        if guild.name == GUILD:
            break

    print(
        f'{discord_bot.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

@discord_bot.event
async def on_message(ctx):
    if ctx.author == discord_bot.user:
        return

    await interpret_ctx_emoji(ctx)

@discord_bot.event
async def on_message_edit(before, ctx):
    print(before.content, ctx.content)
    
    if ctx.author == discord_bot.user:
        return

    print('Message édité')
    await interpret_ctx_emoji(ctx)

if __name__ == "__main__":
    try:
        init_socket()
        if mode_arg == 'Twitch':
            twitch.run()
        elif mode_arg == 'Discord':
            discord_bot.run(os.environ['DISCORD_TOKEN'])
        elif mode_arg == 'Local':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            while True:
                instruction = input()
                ctx = dummy_context(instruction)
                loop.run_until_complete(interpret_ctx_emoji(ctx))
        else:
            raise Exception(mode_arg + ' unknown')
    finally:
        print('Closing')
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

