from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import openai

env_vars = {}
with open('.env') as f:
    for line in f:
        key, value = line.strip().split('=', 1)
        env_vars[key] = value

APP_TOKEN = env_vars["APP_TOKEN"]
BOT_TOKEN = env_vars["BOT_TOKEN"]
openai.api_key = env_vars["OPENAI_KEY"]
app = App(token=BOT_TOKEN)

prompt = """
The following is a conversation with Doug, the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world. Doug is having a conversation with another employee who also works for Moodle.

Human: Hi Doug, how are you?
Doug: I'm doing okay. What's up?
Human: """


def process_query(query):
    engine = 'davinci-instruct-beta'
    split_query = query.split('|')
    if (len(split_query) > 1) and (split_query[1].strip() == 'davinci'):
        engine = 'davinci'


    response = openai.Completion.create(
        engine=engine,
        prompt=prompt + split_query[0] + '\nDoug: ',
        temperature=0.9,
        max_tokens=150,
        top_p=1,
        frequency_penalty=0.0,
        presence_penalty=0.6,
        stop=["Human:"]
    )

    text_response = response['choices'][0]['text']
    text_response = ' '.join(text_response.split('Doug:'))
    print(prompt + split_query[0] + "\nDoug: " + text_response)
    return text_response


@app.event("app_mention")
def mention_handler(body, say):
    print(body)
    say("got it")


@app.event("message")
def message_handler(body, say):
    response = process_query(body['event']['text'])
    print(body)
    say(response)


if __name__ == "__main__":
    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()

