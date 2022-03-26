import string
import requests
import re
import random
import time

import openai
import simplematrixbotlib as botlib
from nio import Api as nio_api

# Read vars from .env
env_vars = {}
with open('.env-test') as f:
    for line in f:
        key, value = line.strip().split('=', 1)
        env_vars[key] = value

openai.api_key = env_vars["OPENAI_KEY"]
MATRIX_SERVER = env_vars["MATRIX_SERVER"]
MATRIX_NAME = env_vars["MATRIX_NAME"]
MATRIX_PW = env_vars["MATRIX_PW"]

# Connect to Matrix
creds = botlib.Creds(MATRIX_SERVER, MATRIX_NAME, MATRIX_PW)
bot = botlib.Bot(creds)
PREFIX = 'DougBot:'

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

default_prompt = """Doug: I am Doug, the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world.
Human: Hi Doug. I'm also an employee at Moodle. Can I ask you a question?
Doug: Absolutely, what's your question? I will give you a short, polite answer."""

help_string = """
Hi, I'm Doug, your AI companion here to give definitely accurate information on all things Moodle! As you've discovered, I will respond to your message when you @ me, like "DougBot: {message}."\n
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

# Doug keeps a rotating queue of the last 20 messages sent in each room, randomly chiming in with context
message_dict = {}
one_on_one_convo_dict = {}


def get_author_and_body_from_message(message):
    """
    Given a message object, return the user who sent it like "@username" and the content of the message, as strings

    Paremeters:
    message (nio.events.room_events.RoomMessageText): The message object corresponding to the message sent

    Return:
    string: The user who sent the message
    string: The content of the message
    """
    message_text = str(message)
    author = message_text.split(': ')[0].split(':')[0]
    body = message_text.split(': ', 1)[1]

    # Remove the "DougBot:" part of the message, if it exists
    if (MATRIX_NAME + ':').lower() in body.lower():
        body = body.split(':', 1)[1]

    return author, body


def process_message_queue(room, message):
    """
    Given a room object and message object, add the message in proper format to the room's running message history

    Parameters:
    room (nio.rooms.MatrixRoom): The room object corresponding to the room the message was sent in
    message (nio.events.room_events.RoomMessageText): The message object corresponding to the message sent
    """
    author, body = get_author_and_body_from_message(message)

    if room.room_id in message_dict:
        message_dict[room.room_id].append({'author': author, 'body': body})

        # Drop leading messages from the queue if longer than 20 entries
        if len(message_dict[room.room_id]) > 20:
            message_dict[room.room_id] = message_dict[room.room_id][len(message_dict[room.room_id])-20:]
    else:
        message_dict[room.room_id] = [{'author': author, 'body': body}]


def process_one_on_one_convo(room, message):
    """
    Given a room object and message object, add the message in proper format to the message history for that specific user in said room
    This way, Doug can carry multiple conversations with people mentioning him

    Parameters:
    room (nio.rooms.MatrixRoom): The room object corresponding to the room the message was sent in
    message (nio.events.room_events.RoomMessageText): The message object corresponding to the message sent
    """
    author, body = get_author_and_body_from_message(message)

    if room.room_id in one_on_one_convo_dict:
        if author in one_on_one_convo_dict[room.room_id]:
            # one-on-one context is cleared after 5 minutes
            if time.time() - one_on_one_convo_dict[room.room_id][author]['last_accessed'] > 300:
                one_on_one_convo_dict[room.room_id][author]['message_list'] = []

            one_on_one_convo_dict[room.room_id][author]['message_list'].append({'author': author, 'body': body})
            one_on_one_convo_dict[room.room_id][author]['last_accessed'] = time.time()
        else:
            one_on_one_convo_dict[room.room_id][author] = {'message_list': [{'author': author, 'body': body}], 'last_accessed': time.time()}
    else:
        one_on_one_convo_dict[room.room_id] = {author: {'message_list': [{'author': author, 'body': body}], 'last_accessed': time.time()}}


def process_query(query, prompt):
    """
    Fetches a completion from OpenAI when given a prompt and a query (The query gets appended to the prompt before sending)

    Parameters:
    query (string): The message to append to the prompt before sending, probably provided by a user mentioning Doug in a message
    prompt (string): The context string to append the message to

    Returns:
    string: A completed string from OpenAI
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


def process_history(room=None, event=None, message_list=None, prompt=None):
    """
    Takes an event object or list of messages and formats it into a string that can be passed as a prompt to process_query

    Parameters:
    room (nio.rooms.MatrixRoom) optional: The room object corresponding to the room that we want to get context from, if applicable
    event (nio.events.room_events.Event) optional: The event that we want context around, if applicable -- probably RoomMessageText
    message_list (list) optional: A list of previous messages to use as context, if applicable
    prompt (string) optional: A custom prompt to use in order to build the final prompt string, if applicable

    Return:
    string: The final formatted prompt, including the context discovered or passed to this function
    """
    # If a custom prompt wasn't explicitly passed, just use the default
    if not prompt:
        prompt = default_prompt

    # If an Event object was passed, use the API to get surrounding context and build a prompt from that
    if event and room:
        api_params = nio_api.room_context(MATRIX_TOKEN, room.room_id, event.event_id)
        response = requests.get(MATRIX_SERVER + api_params[1]).json()

        if 'events_before' in response:
            for event in reversed(response['events_before']):
                username = re.split('[^a-zA-Z]', event['sender'][1:])[0]
                prompt += '\n' + username + ': ' + event['content']['body']

    # If a message list was passed, build the prompt from that instead
    elif message_list:
        for event in message_list:
            prompt += '\n' + event['author'] + ': ' + event['body']

    return prompt


@bot.listener.on_message_event
async def echo(room, message):
    match = botlib.MessageMatch(room, message, bot, PREFIX)

    prompt = default_prompt
    author, body = get_author_and_body_from_message(message)

    process_message_queue(room, message)

    if match.prefix():
        if body.lower().strip() == "help":
            await bot.api.send_text_message(room.room_id, help_string)
            return

        if 'what do you think' in body.lower() or body[0] == '*':
            prompt = process_history(room=room, event=message)
        else:
            process_one_on_one_convo(room, message)
            prompt = """Doug is the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world. Below is a transcript from a conversation that he is having with another employee:\n"""
            prompt = process_history(message_list=one_on_one_convo_dict[room.room_id][author]['message_list'], prompt=prompt)

        # Sometimes OpenAI just outputs garbage, like a string only including whitespace and punctuation 
        # This loop keeps asking for completions until we get something more sane
        # (although this may only apply to Slack and not Matrix for reasons I don't feel like writing here)
        response = ''
        while response.translate(str.maketrans('', '', string.punctuation)).strip() == '':
            response = process_query(body, prompt)

        if room.room_id in one_on_one_convo_dict and author in one_on_one_convo_dict[room.room_id]:
            one_on_one_convo_dict[room.room_id][author]['message_list'].append({'author': 'Doug', 'body': response})

        await bot.api.send_text_message(room.room_id, response)

    else:
        # If a message has come in not directed at Doug (and not from Doug himself), give a 20% chance of chiming into the conversation
        # Context provided by the message_dict var goes back 20 messages
        if random.uniform(0, 1000) <= 333 and author != '@' + MATRIX_NAME:
            prompt = """Doug is the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world. Below is a transcript from a conversation that he is a part of:\n"""
            prompt = process_history(message_list=message_dict[room.room_id], prompt=prompt)

            response = ''
            while response.translate(str.maketrans('', '', string.punctuation)).strip() == '':
                response = process_query(body, prompt)

            await bot.api.send_text_message(room.room_id, response)


bot.run()
