from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import openai

# Read vars from .env
env_vars = {}
with open('.env') as f:
    for line in f:
        key, value = line.strip().split('=', 1)
        env_vars[key] = value

APP_TOKEN = env_vars["APP_TOKEN"]
BOT_TOKEN = env_vars["BOT_TOKEN"]
BOT_ID = env_vars["BOT_ID"]
openai.api_key = env_vars["OPENAI_KEY"]

app = App(token=BOT_TOKEN)

prompt = """
The following is a conversation with Doug, the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world. Doug is having a conversation with another employee who also works for Moodle.

Human: Hi Doug, how are you?
Doug: I'm doing okay. What's up?
Human: """


def process_query(query, query_prompt=prompt):
    """
    Takes a query string (usually a question) and optionally a prompt string, passes it to OpenAI, and returns a response
    If unspecified, uses the global prompt variable
    """
    # Allow the user to determine the engine to use
    # ie, "What is your favorite animal | davinci" will use the davinci engine; defaults to davinci-instruct-beta
    engine = 'davinci-instruct-beta'
    split_query = query.split('|')
    if (len(split_query) > 1) and (split_query[1].strip() == 'davinci'):
        engine = 'davinci'

    response = openai.Completion.create(
        engine=engine,
        prompt=query_prompt + split_query[0] + '\nDoug: ',
        temperature=0.9,
        max_tokens=150,
        top_p=1,
        frequency_penalty=0.0,
        presence_penalty=0.6,
        stop=["Human:"]
    )

    text_response = response['choices'][0]['text']
    text_response = ' '.join(text_response.split('Doug:')) # We don't want the bot to actually SAY "Doug:" in the response
    print(prompt + split_query[0] + "\nDoug: " + text_response)

    if text_response == '':
        text_response = ':)'

    return text_response


def format_conversation_prompt(convo_data):
    """
    Takes a Slack conversation object from conversations.history and formats it into/returns a prompt string to be ingested by OpenAI
    """
    real_prompt = prompt
    for index, message in enumerate(convo_data[::-1]):
        user = 'Human: '
        if 'bot_id' in message:
            user = 'Doug: '
        if index == 0:
            real_prompt += message['text'] + "\n"
        else:
            real_prompt += user + message['text'] + "\n"
    real_prompt = real_prompt.replace('<@' + BOT_ID + '>', '') # Remove internal Slack ID
    print('real prompt:')
    print(real_prompt)
    real_prompt += "\nDoug: "
    return real_prompt


@app.event("app_mention")
def mention_handler(body, say):
    """
    When the bot is mentioned, process a response
    """
    response = None
    query = body['event']['text'].replace('<@' + BOT_ID + '>', '')
    # If the string contains "what do you think," Doug will summarize the last 10 messages of the current conversation
    # Otherwise, only respond to the message he was tagged in
    if 'what do you think' in query.lower():
        channel_id = body['event']['channel']
        convo_data = app.client.conversations_history(channel=channel_id, limit=10)
        real_prompt = format_conversation_prompt(convo_data['messages'])
        response = process_query(query, query_prompt=real_prompt)
    else:
        response = process_query(query)
    say(response)


@app.event("message")
def message_handler(body, say):
    """
    When the bot receives a DM, respond to it
    """
    response = process_query(body['event']['text'])
    say(response)


if __name__ == "__main__":
    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()

