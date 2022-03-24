import openai
import string
import requests
import re
import simplematrixbotlib as botlib
from nio import Api as nio_api

# Read vars from .env
env_vars = {}
with open('.env') as f:
    for line in f:
        key, value = line.strip().split('=', 1)
        env_vars[key] = value

openai.api_key = env_vars["OPENAI_KEY"]
MATRIX_SERVER = env_vars["MATRIX_SERVER"]
MATRIX_NAME = env_vars["MATRIX_NAME"]
MATRIX_PW = env_vars["MATRIX_PW"]

original_prompt = """Doug: I am Doug, the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world.
Human: Hi Doug. I'm also an employee at Moodle. Can I ask you a question?
Doug: Absolutely, what's your question? I will give you a short, polite answer."""

help_string = """
Hi, I'm Doug, your AI companion here to give definitely accurate information on all things Moodle! As you've discovered, I will respond to your message when you @ me, like "@doug_bot {message}."\n
You can say 'help' to see this message. Anything else I will try my best to answer. \n
I'm powered by OpenAI's GPT-3, and you can specify the engine you want to use by separating your message with a pipe. For example, you can say "@doug_bot How are you today? | text-ada-001" to generate an answer with the Ada engine. By default, I use text-davinci-002. You can find a list of available engines here: https://beta.openai.com/docs/engines/gpt-3\n
By default, I only respond to the message I am tagged in. However, if the phrase "what do you think" occurs anywhere in your message, or the first character of your message is an asterisk (*), I will consider the last 6 messages in the chat before I respond.
"""

engines = [
    'text-davinci-002',
    'text-curie-001',
    'text-babbage-001',
    'text-ada-001'
]

# Connect to Matrix
creds = botlib.Creds(MATRIX_SERVER, MATRIX_NAME, MATRIX_PW)
bot = botlib.Bot(creds)
PREFIX = 'DougBot'

# Get access token
token_request = {
    "type": "m.login.password",
    "identifier": {
        "type": "m.id.user",
        "user": MATRIX_NAME
    },
    "password": MATRIX_PW
}
response = requests.post(MATRIX_SERVER + '/_matrix/client/v3/login', json=token_request).json()
MATRIX_TOKEN = response['access_token']


def process_query(query, prompt):
    """
    Takes a query string (usually a question) and a prompt string, passes it to OpenAI, and returns a response
    """
    # Allow the user to determine the engine to use
    # ie, "What is your favorite animal | text-ada-001" will use the ada engine; defaults to text-davinci-002
    engine = 'text-davinci-002'
    split_query = query.split('|')
    if (len(split_query) > 1) and (split_query[1].strip() in engines):
        engine = split_query[1].strip()

    response = openai.Completion.create(
        engine=engine,
        prompt=prompt + '\nHuman: ' + split_query[0] + '\nDoug: ',
        temperature=0.9,
        max_tokens=500,
        top_p=1,
        frequency_penalty=1.0,
        presence_penalty=0.6,
        stop=["Human:"]
    )

    text_response = response['choices'][0]['text']
    text_response = ' '.join(text_response.split('Doug:')) # We don't want the bot to actually SAY "Doug:" in the response
    print('full message:')
    print(prompt + '\nHuman: ' + split_query[0] + "\nDoug: " + text_response.lstrip())

    return text_response.lstrip()


def process_history(room, event):
    """
    Takes a room ID and event object, and returns a formatted, multiline string of surrounding message context to be given to OpenAI 
    """
    api_params = nio_api.room_context(MATRIX_TOKEN, room.room_id, event.event_id)
    response = requests.get(MATRIX_SERVER + api_params[1]).json()
    prompt = original_prompt

    if 'events_before' in response:
        for event in reversed(response['events_before']):
            username = re.split('[^a-zA-Z]', event['sender'][1:])[0]
            prompt += '\n' + username + ': ' + event['content']['body']

    return prompt


@bot.listener.on_message_event
async def echo(room, message):
    match = botlib.MessageMatch(room, message, bot, PREFIX)
    message_text = " ".join(arg for arg in match.args())

    if match.prefix() and match.command(":"):

        if message_text.lower().strip() == "help":
            await bot.api.send_text_message(room.room_id, help_string)
            return

        prompt = original_prompt
        if 'what do you think' in message_text.lower() or message_text[0] == '*':
            prompt = process_history(room, message)

        response = ''
        while response.translate(str.maketrans('', '', string.punctuation)).strip() == '':
            response = process_query(message_text, prompt)

        await bot.api.send_text_message(room.room_id, response)


bot.run()
