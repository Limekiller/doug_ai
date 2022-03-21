import openai
import string
import simplematrixbotlib as botlib

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

prompt = """
Doug: I am Doug, the creator of Moodle. Moodle is an LMS (learning management system), the most popular open-source LMS in the world.
Human: Hi Doug. I'm also an employee at Moodle. Can I ask you a question?
Doug: Absolutely, what's your question? I will give you a short, polite answer.
Human: """

engines = [
    'text-davinci-002',
    'text-curie-001',
    'text-babbage-001',
    'text-ada-001'
]

# Connect to Matrix
creds = botlib.Creds(MATRIX_SERVER, MATRIX_NAME, MATRIX_PW)
bot = botlib.Bot(creds)
PREFIX = '@'


def process_query(query, query_prompt=prompt):
    """
    Takes a query string (usually a question) and optionally a prompt string, passes it to OpenAI, and returns a response
    If unspecified, uses the global prompt variable
    """
    # Allow the user to determine the engine to use
    # ie, "What is your favorite animal | text-ada-001" will use the ada engine; defaults to text-davinci-002
    engine = 'text-davinci-002'
    split_query = query.split('|')
    if (len(split_query) > 1) and (split_query[1].strip() in engines):
        engine = split_query[1].strip()

    response = openai.Completion.create(
        engine=engine,
        prompt=query_prompt + split_query[0] + '\nDoug: ',
        temperature=0.9,
        max_tokens=75,
        top_p=1,
        frequency_penalty=1.0,
        presence_penalty=0.6,
        stop=["Human:"]
    )

    text_response = response['choices'][0]['text']
    text_response = ' '.join(text_response.split('Doug:')) # We don't want the bot to actually SAY "Doug:" in the response
    print('full message:')
    print(prompt + split_query[0] + "\nDoug: " + text_response)

    return text_response


@bot.listener.on_message_event
async def echo(room, message):
    match = botlib.MessageMatch(room, message, bot, PREFIX)
    message = " ".join(arg for arg in match.args())

    if match.prefix() and match.command("doug_ai"):

        response = ''
        while response.translate(str.maketrans('', '', string.punctuation)).strip() == '':
            response = process_query(message)

        await bot.api.send_text_message(room.room_id, response)


bot.run()
