import time
import os
import json
import logging as log
from openai import OpenAI
from src.utils import gpt_cost_calculator


def checkFormat(response: dict)->bool:
    """
    Check if the response is in the correct format

    response : {
        "targets" : {type:List(str)},
        "queries" : { type : Dict(str:str)}
    }
    """
    if "targets" not in response:
        return False
    # if not isinstance(response["targets"], list):
    #     return False
    if "queries" not in response:
        return False
    if "web" not in response["queries"]:
        return False
    return True

def generate_search_query(prompt: str,open_api_key:str, location: str = None) -> json:
    """
    Sanitize the search query using OpenAI for web search
    """
    t_flag1 = time.time()

    if open_api_key is None:
        try:
            open_api_key = os.getenv("OPENAI_API_KEY")
        except Exception as e:
            log.error(f"No Open API key found")
            raise e

    prompt = f"{prompt.strip()}"
    client = OpenAI(api_key=open_api_key)

    system_prompt = """
Comprehend the goal, and provide small web search queries to assist in achieving it. The queries should be based on finding the email of best individual person or an expert, to contact for helping or completing the user goal. First give the list of people/vendor (1 to 3) to approach for the goal (Eg- Professors, Catering Companies etc) in small strings as targets (focus on a person in 1-3 words). Then give search queries, always give search queries for `web` in a list of string(max 3), each targeting a target and slightly broaden the search(searching for their email). `yelp` and `gmaps` both are used for searching local businesses, including personal, small, and medium-sized enterprises, use whenever location is given, else give an empty string. The output should be in JSON format : "{\"targets\": [\"\",\"\"], \"queries\": {\"web\": [\"\", \"\"...], \"yelp\": \"...\", \"gmaps\": \"...\"}}
"""
# 'yelp' search query should NOT include location in its query string (Yelp does not accept location based search query, only vendor).

    try:
        response = client.chat.completions.create(
            model="ft:gpt-3.5-turbo-1106:margati:querysanitation:93po9nBX",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": f"{system_prompt}"},
                {"role": "user", "content": f"Goal: {prompt}; User's location- {location};"},
            ],
        )
    except Exception as e:
        log.error(f"Error in OpenAI query sanitation: {e}")
        exit(1)

    t_flag2 = time.time()
    log.info(f"OpenAI Query generation time: {t_flag2 - t_flag1}\n")

    # cost 
    cost = gpt_cost_calculator(
        response.usage.prompt_tokens, response.usage.completion_tokens, model='gpt-3.5-turbo-finetune'
    )
    log.info(f"Cost for search query sanitation: ${cost}")
    try:
        result = json.loads(response.choices[0].message.content)
        log.info(f"\nSearch Query is : {result}\n")
        
        if not checkFormat(result):
            log.error(f"Invalid format of response")
            raise Exception("Invalid format of response of query generation")
        
    except Exception as e:
        log.error(f"Error parsing json: {e}")
        raise Exception("Error parsing json of query generation")
    return result


