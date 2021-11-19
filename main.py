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
Background:
I am Doug.
Moodle is an LMS (learning management system).
Moodle is the most popular open-source LMS in the world.
We work for Moodle.
I created Moodle.

"""


@app.event("app_mention")
def mention_handler(body, say):
    print(body)
    say("got it")


@app.event("message")
def message_handler(body, say):
    print(body)
    response = openai.Completion.create(
        engine="davinci",
        prompt=prompt + "\nQuestion: " + body['event']['text'] + "\nPolite response: ",
        temperature=0.9,
        max_tokens=150,
        top_p=1,
        frequency_penalty=0.0,
        presence_penalty=0.6,
        stop=[".", "!"]
    )
    say(response['choices'][0]['text'])

if __name__ == "__main__":
    handler = SocketModeHandler(app, APP_TOKEN)
    handler.start()
