from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI
import string
import time
import random
import re

# Read vars from .env
env_vars = {}
with open('.env-test') as f:
    for line in f:
        key, value = line.strip().split('=', 1)
        env_vars[key] = value

APP_TOKEN = env_vars["APP_TOKEN"]
BOT_TOKEN = env_vars["BOT_TOKEN"]
BOT_ID = env_vars["BOT_ID"]

app = App(token=BOT_TOKEN)
client = OpenAI(
    api_key=env_vars["OPENAI_KEY"]
)

PROMPT = """
You are Doug, the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world. 
You aren't an assistant, you're just always having conversations with your coworkers. You may be talking to multiple people at the same time.
You try to be friendly, but sometimes let yourself get snarky -- and always bring the conversation back to Moodle!
"""

ENGINES = [
    'gpt-4',
    'gpt-4-1106-preview',
    'gpt-4-0613',
    'gpt-4-0314',
    'gpt-3.5-turbo',
    'gpt-3.5-turbo-16k',
    'gpt-3.5-turbo-1106',
    'gpt-3.5-turbo-0613',
    'gpt-3.5-turbo-16k-0613',
]

CHANNELS_DOUG_CAN_CHIME_IN = [
    'C03C43ZME77',
    # 'C02EYENFY4R'
]

COVERSATION_DICT = {'channels': {}, 'DMs': {}}

def get_response(query, message_list=[]):
    """
    Takes a query and a list of messages and returns a completion
    """
    message_list.insert(0, {
        "role": "system",
        "content": PROMPT
    })

    message_list.append({
        "role": "user",
        "content": query
    })

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=message_list
    )

    return response.choices[0].message.content


def get_thread_messages(channel_id, thread_id):
    """
    Given a channel and thread ID, get a formatted list of messages from the thread
    """
    messages = []

    thread_messages = app.client.conversations_replies(
        channel=channel_id,
        ts=thread_id
    )

    thread_messages['messages'].pop()
    for message in thread_messages['messages']:
        role = 'assistant'
        if message['user'] != 'Doug':
            role = 'user'

        text = message['text']
        content = insert_pretty_names(text)
        messages.append({'role': role, 'content': content})

    return messages


def insert_pretty_names(content):
    """
    Given a string containing Slack IDs like '.... <@ID> ....', split it up into tokens consisting of either a string or a Slack ID
    Then replace each ID with the user's real name and return the combined sentence
    """
    sentence = []
    tokens = [token for token in re.split(r'(<[^>]*>)', content) if token]
    for token in tokens:
        if token[0] == '<' and token[1] == '@' and token[-1] == '>':
            user_id = token.split('<@')[1].split('>')[0]
            user = '@' + app.client.users_profile_get(user=user_id)['profile']['real_name']
            sentence.append(user)
        else:
            sentence.append(token)

    return ''.join(sentence)


def get_message_history(user=None, channel=None):
    """
    This function takes a user or channel ID, and returns the message history for that user or channel
    """
    message_list = []
    # determine which source to pull the message list from
    if channel:
        if channel not in COVERSATION_DICT['channels']:
            return False
        message_list = COVERSATION_DICT['channels'][channel]['messages']
    else:
        if user not in COVERSATION_DICT['DMs']:
            return []
        message_list = COVERSATION_DICT['DMs'][user]['messages']

    return message_list
def record_conversation(user, role, content, channel=None):
    """
    This function stores responses in a dictionary for later retrieval
    """
    if channel:
        if channel in COVERSATION_DICT['channels']:
            # reset convo if response time is greater than 10 minutes
            if time.time() - COVERSATION_DICT['channels'][channel]['time'] > 600:
                COVERSATION_DICT['channels'][channel]['messages'] = []

            COVERSATION_DICT['channels'][channel]['messages'].append({'role': role, 'content': content})
            COVERSATION_DICT['channels'][channel]['time'] = time.time()
        else:
            COVERSATION_DICT['channels'][channel] = {'messages': [{'role': role, 'content': content}], 'time': time.time()}
    else:
        if user in COVERSATION_DICT['DMs']:
            if time.time() - COVERSATION_DICT['DMs'][user]['time'] > 600:
                COVERSATION_DICT['DMs'][user]['messages'] = []

            COVERSATION_DICT['DMs'][user]['messages'].append({'role': role, 'content': content})
            COVERSATION_DICT['DMs'][user]['time'] = time.time()
        else:
            COVERSATION_DICT['DMs'][user] = {'messages': [{'role': role, 'content': content}], 'time': time.time()}


def channel_handler(body, say):
    content = insert_pretty_names(body['event']['text'])
    channel_id = body['event']['channel']

    thread_id = None
    if 'thread_ts' in body['event']:
        thread_id = body['event']['thread_ts']

    randomChanceCheck = random.randint(0, 100) < 20
    messageInValidChannel = body['event']['channel'] in CHANNELS_DOUG_CAN_CHIME_IN
    messageWasJustSent = time.time() - body['event_time'] < 10

    if randomChanceCheck and messageInValidChannel and messageWasJustSent:
        # If the message was in a thread, get a list of all thread messages for context
        # otherwise use our convo dict
        if thread_id:
            messages = get_thread_messages(channel_id, thread_id)
            response = get_response(content, messages)
        
            app.client.chat_postMessage(
                channel = channel_id,
                thread_ts = thread_id,
                text = response
            )
        else:
            record_conversation(body['event']['user'], "user", content, channel_id)
            messages = get_message_history(channel=channel_id)
            response = get_response(content, messages)
            record_conversation(body['event']['user'], "assistant", response, channel_id)
            say(response)
    else:
        if not thread_id:
            record_conversation(body['event']['user'], "user", content, channel_id)
    
    print(COVERSATION_DICT)


def im_handler(body, say):
    """
    When the bot receives a DM, respond to it
    """
    record_conversation(body['event']['user'], "user", body['event']['text'])

    messages = get_message_history(user=body['event']['user'])
    response = get_response(body['event']['text'], messages)
    record_conversation(body['event']['user'], "assistant", response)

    print(COVERSATION_DICT)
    say(response)


@app.event("message")
def message_handler(body, say):
    """ 
    Slack listener for *any* message
    """
    if body['event']['channel_type'] == 'im':
        # Handle a DM
        im_handler(body, say)
    else:
        channel_handler(body, say)


@app.event("app_mention")
def mention_handler(body, say):
    """
    Slack listener for pings ("@doug_ai")
    """

    channel_id = body['event']['channel']
    content = insert_pretty_names(body['event']['text'])

    # If the message is part of a thread, respond in that thread
    if 'thread_ts' in body['event']:
        thread_id = body['event']['thread_ts']
        messages = get_thread_messages(channel_id, thread_id)
        response = get_response(content, messages)
        app.client.chat_postMessage(
            channel = channel_id,
            thread_ts = thread_id,
            text = response
        )

    else:
        record_conversation(body['event']['user'], "user", content, channel_id)
        messages = get_message_history(channel=channel_id)
        response = get_response(content, messages)
        record_conversation(body['event']['user'], "assistant", response, channel_id)
        say(response)


if __name__ == "__main__":
    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()
