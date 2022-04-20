from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import openai
import string
import time

# Read vars from .env
env_vars = {}
with open('.env-test') as f:
    for line in f:
        key, value = line.strip().split('=', 1)
        env_vars[key] = value

APP_TOKEN = env_vars["APP_TOKEN"]
BOT_TOKEN = env_vars["BOT_TOKEN"]
BOT_ID = env_vars["BOT_ID"]
openai.api_key = env_vars["OPENAI_KEY"]

app = App(token=BOT_TOKEN)

prompt = """
Doug: I am Doug, the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world.
Human: Hi Doug. I'm also an employee at Moodle. Can I ask you a question?
Doug: Absolutely, what's your question? I can give you a quick, polite answer.
Human: """

engines = [
    'text-davinci-002',
    'text-curie-001',
    'text-babbage-001',
    'text-ada-001'
]

conversation_dict = {'channels': {}, 'DMs': {}}

def process_query(query, prompt=prompt):
    """
    Takes a query string (usually a question) and optionally a prompt string, passes it to OpenAI, and returns a response
    If unspecified, uses the global prompt variable
    """
    # Allow the user to determine the engine to use
    # ie, "What is your favorite animal | davinci" will use the davinci engine; defaults to davinci-instruct-beta
    engine = 'text-davinci-002'
    split_query = query.split('|')
    if (len(split_query) > 1) and (split_query[1].strip() in engines):
        engine = split_query[1].strip()

    response = openai.Completion.create(
        engine=engine,
        prompt=prompt + split_query[0] + '\nDoug: ',
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
    print(prompt + split_query[0] + "\nDoug: " + text_response.strip())

    return text_response.strip()


def format_message_history_prompt(user, channel=None):
    new_prompt = prompt
    message_list = []

    # determine which source to pull the message list from
    if channel:
        if channel not in conversation_dict['channels']:
            return new_prompt
        new_prompt = """Doug is the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world. The following is a transcript from a conversation he is having with multiple employees:\n"""
        message_list = conversation_dict['channels'][channel]['messages']
    else:
        if user not in conversation_dict['DMs']:
            return new_prompt
        new_prompt = """Doug is the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world. The following is a transcript from a conversation he is having with an employee:\n"""
        message_list = conversation_dict['DMs'][user]['messages']

    for message in message_list:
        user = 'Doug'
        if message['user'] != 'Doug':
            user = 'Employee'
        new_prompt += user + ': ' + message['body'] + "\n"
    new_prompt += "Employee: "

    return new_prompt


def record_conversation(user, body, channel=None):
    if channel:
        if channel in conversation_dict['channels']:
            # reset convo if response time is greater than 10 minutes
            if time.time() - conversation_dict['channels'][channel]['time'] > 600:
                conversation_dict['channels'][channel]['messages'] = []

            conversation_dict['channels'][channel]['messages'].append({'user': user, 'body': body})
            conversation_dict['channels'][channel]['time'] = time.time()
        else:
            conversation_dict['channels'][channel] = {'messages': [{'user': user, 'body': body}], 'time': time.time()}
    else:
        if user in conversation_dict['DMs']:
            if time.time() - conversation_dict['DMs'][user]['time'] > 600:
                conversation_dict['DMs'][user]['messages'] = []

            conversation_dict['DMs'][user]['messages'].append({'user': user, 'body': body})
            conversation_dict['DMs'][user]['time'] = time.time()
        else:
            conversation_dict['DMs'][user] = {'messages': [{'user': user, 'body': body}], 'time': time.time()}


@app.event("app_mention")
def mention_handler(body, say):
    """
    When the bot is mentioned, process a response
    """
    response = ''
    query = body['event']['text'].replace('<@' + BOT_ID + '>', '')
    channel_id = body['event']['channel']

    ai_prompt = format_message_history_prompt(body['event']['user'], channel_id)
    response = process_query(query, ai_prompt)

    # If the message is part of a thread, respond in that thread
    if 'thread_ts' in body['event']:
        app.client.chat_postMessage(
            channel = channel_id,
            thread_ts = body['event']['thread_ts'],
            text = response
        )

    else:
        record_conversation(body['event']['user'], query, channel_id)
        conversation_dict['channels'][channel_id]['messages'].append({'user': 'Doug', 'body': response})
        print(conversation_dict)

        say(response)


@app.event("message")
def message_handler(body, say):
    """
    When the bot receives a DM, respond to it
    """
    response = ''
    ai_prompt = format_message_history_prompt(body['event']['user'])
    response = process_query(body['event']['text'], ai_prompt)

    record_conversation(body['event']['user'], body['event']['text'])
    conversation_dict['DMs'][body['event']['user']]['messages'].append({'user': 'Doug', 'body': response})
    print(conversation_dict)

    say(response)


if __name__ == "__main__":
    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()

