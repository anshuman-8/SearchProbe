import os
from openai import OpenAI
import json
from dotenv import load_dotenv

load_dotenv()

MY_ENV_VAR = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=MY_ENV_VAR)
print("client ready")

sys_prompt = """
Comprehend the goal, and provide small web search queries to assist in achieving it. The queries should be based on finding the email of best individual person or an expert, to contact for helping or completing the user goal. First give the list of people/vendor (1 to 3) to approach for the goal (Eg- Professors, Catering Companies etc) in small strings as targets (focus on a person in 1-3 words). Then give search queries, always give search queries for `web` in a list of string(max 3), each targeting a target and slightly broaden the search(searching for their email). Give yelp and gmaps search query only if necessary for the goal.`yelp` and `gmaps` both are used for local businesses, including personal, small, and medium-sized enterprises, use both only when location is given by user (but don't use near me), else give an empty string. 'yelp' search query should NOT include location in its query string (Yelp does not accept location based search query, only vendor). The output should be in JSON format : "{\"targets\": [\"\",\"\"], \"queries\": {\"web\": [\"\", \"\"...], \"yelp\": \"\", \"gmaps\": \"\"}}
"""

train_sys_prompt = """
Comprehend the goal, and provide small web search queries to assist in achieving it. The queries should be based on finding the email of best individual person or an expert, to contact for helping or completing the user goal. First give the list of people/vendor to approach for the goal in small strings as targets (focus on a person). Then give search queries, always give search queries for `web` in a list of string, each targeting a target and slightly broaden the search. 'yelp' search query should not include location in its query string. The output should be in JSON format : "{\"targets\": [\"\",\"\"], \"queries\": {\"web\": [\"\", \"\"...], \"yelp\": \"\", \"gmaps\": \"\"}}
"""
i=0

def gpt4_response_string(goal):
    response = client.chat.completions.create(
        model= "gpt-4-1106-preview",
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Goal:{goal}"},
        ]
    )
    response = json.loads(response.choices[0].message.content)
    return json.dumps(response)

def display_response(response):
    print(response)

fail_file = "./data/fail_goals.txt"
dataset_file = "./data/query_generation.jsonl"

with open('./data/goals.txt', 'r') as file:
    for line in file:
        goal = line[1:].strip()
        print("index: ",i, "  Goal: ", goal)
        
        try:
            response = gpt4_response_string(goal)
        except Exception as e:
            print(e)
            with open(fail_file, 'a') as f:
                f.write(f"{goal}\n")
            continue

        display_response(response)
        
        # ask for user input if Enter then continue if n the skip if e then exit
        inp = input("\nEnter to continue, n to skip, e to exit\n:")
        i+=1
        if inp == "n":
            with open(fail_file, 'a') as f:
                f.write(f"{goal}\n")
        elif inp == "e":
            break
        else:
            val = {"messages":[{"role": "system", "content": train_sys_prompt},{"role": "user", "content": goal},{ "role": "assistant", "content": response}]}
            # wirte to file dataset file
            with open(dataset_file, 'a') as f:
                f.write(json.dumps(val) + "\n")
            print("\n\n")

print("done")


        


        
