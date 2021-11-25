# doug_ai
Doug is a GPT3-powered Slack chatbot, leveraging OpenAI's API. He is prompted to respond to any query as if he is the creator of Moodle, and he is given a short background about Moodle in said prompt. This makes his responses more likely to be within the relevant context.

![image](https://user-images.githubusercontent.com/33644013/142739607-6299a303-563a-44dd-a338-0f0174671a65.png)
## Using
Doug will respond to direct messages on an individual basis, interpreting each message as a separate question. If Doug has joined a channel, he can be tagged and will respond to the message in which he is tagged -- again, on an individual basis, without considering the surrounding message context. If the string "what do you think" is contained in the message in which Doug is tagged, he will consider the last 10 messages in the channel before responding.

By default, Doug will use the `davinci-instruct-beta` engine. Users can manually choose to process the query with the `davinci` engine instead by "piping" the query into it: ie, "What is your favorite color, Doug? | davinci"

I am planning to generalize this functionality to allow any GPT3 engine to be selected by the user.
## Installing
- set up a Slack chat bot with the following scopes:
  + App-Level token: connections:write
  + Bot token: app_mentions:read
  + Bot token: channels:history
  + Bot token: channels:read
  + Bot token: chat:write
  + Bot token: groups:history
  + Bot token: im:history
  + Bot token: im:write
  + Bot token: mpim:write
- install bot to workspace and copy bot's "member ID"
- clone project
- `python3 install -r requirements.txt`
- create .env file with following values:
  + APP_TOKEN=slack app token
  + BOT_TOKEN=slack bot token
  + BOT_ID=member ID copied above
  + OPENAI_KEY=openAI API key
- Run the script!
