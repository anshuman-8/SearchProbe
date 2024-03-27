import time
import json
import asyncio
import logging as log
from openai import AsyncOpenAI, OpenAI
from typing import Iterator, List

from src.utils import inflating_retrieval_results, gpt_cost_calculator

LOG_FILES = False


SYS_PROMPT = """Extract all vendors/peoples and their contact details from internet scraped context, aiming to assist the user's goal in finding the right service providers or vendors with contacts from the target list. Only retrieve the contacts of vendor/person that can server the user's goal (in targets), skip all unrelated.
The response should strictly adhere to the JSON format: {"results": [{"contacts": {"email": "(string)vendor email", "phone": "(string)vendor phone number"},"id":(int)correct id of the json data given in Context,"name": "(string)Name of the vendor helping the goal", "target":"(string) which category from the target list"}, {...}]}.
Use an empty string if any data is absent or is not available. Strictly avoid providing incorrect contact details. Give phone numbers and emails in usable and correct format (no helper words). If contact information is unavailable or not enough, just omit or skip the vendor or person. Give only one email and one phone number for each vendor/person.
Do not give dummy or example data. Make sure the phone number is in E.164 format, based on country. Give empty list [], if not vendor details are given in the context. Always give correct id of the json content used for contact retrieval.
\nExample response (Only as an example format, data not to be used) : \n{"results": [{"contacts": {"email": "oakland@onetoyota.com","phone": "+15102818909"},"id":2, "name": "One Toyota Oakland", "target":"Car rentals"}]}\n"""

## ------------------------ Async ------------------------ ##


def result_to_json(results: List[dict]) -> dict:
    """
    Convert the list of contacts to json
    """
    json_result = {"results": []}
    for result in results:
        if result == {}:
            continue

        json_result["results"].extend(result["results"])
    return json.dumps(json_result)


def print_and_write_response(response_json, output_file="output.txt"):
    """
    Print and write the response to a file
    """
    print("\n")

    if isinstance(response_json, dict) and "results" in response_json:
        results = response_json["results"]
    elif isinstance(response_json, list):
        results = response_json
    else:
        print("Invalid input. Please provide a valid JSON object or a list of them.")
        return

    with open(output_file, "a") as file:
        for service in results:
            file.write(f"Service Provider: {service.get('service_provider', '')}\n")
            file.write(f"Source: {service.get('source', '')}\n")

            contacts = service.get("contacts", {})
            file.write(f"Contacts:\n")
            file.write(f"\tEmail: {contacts.get('email', '')}\n")
            file.write(f"\tPhone: {contacts.get('phone', '')}\n")
            # file.write(f"\tAddress: {contacts.get('address', '')}\n")

            file.write("\n" + "-" * 40 + "\n\n")

            # Print to console
            print(f"Service Provider: {service.get('service_provider', '')}")
            print(f"Source: {service.get('source', '')}")
            print(f"Contacts:")
            print(f"\tEmail: {contacts.get('email', '')}")
            print(f"\tPhone: {contacts.get('phone', '')}")
            # print(f"\tAddress: {contacts.get('address', '')}")
            print("\n" + "-" * 40 + "\n")


async def extract_thread_contacts(
    id: int, data, prompt: str, targets: List[str] | None, openai_client: OpenAI
) -> json:
    """
    Extract the contacts from the search results using LLM
    """

    t_flag1 = time.time()
    log.info(f"Contact Retrival Thread {id} started")


    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": SYS_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"Context: {data}\n\nGoal: {prompt}\nTargets: {targets}\nAnswer:All relevant and accurate contact details for above Question in JSON:",
                },
            ],
        )

        t_flag2 = time.time()
        log.info(f"OpenAI time: { t_flag2 - t_flag1}")

        cost = gpt_cost_calculator(
            response.usage.prompt_tokens, response.usage.completion_tokens
        )
        log.debug(
            f"Input Tokens used: {response.usage.prompt_tokens}, Output Tokens used: {response.usage.completion_tokens}"
        )
        log.info(f"Cost for contact retrival {id}: ${cost}")

        response = json.loads(response.choices[0].message.content)

        log.info(f"Contact Retrival Thread {id} finished : {response}\n")

    except Exception as e:
        log.error(f"Error in {id} LLM API call: {e}")
        response = {}

    return response


async def retrieval_multithreading(
    data,
    prompt: str,
    solution: str | None,
    open_ai_key: str,
    context_chunk_size: int = 5,
    max_thread: int = 5,
    timeout: int = 10,
):
    """
    Creates multiple LLM calls
    """
    # Divide the data into chunks of size chunk_size
    data_chunks = [
        data[i : i + context_chunk_size]
        for i in range(0, len(data), context_chunk_size)
    ]
    data_chunks = data_chunks[:max_thread]

    log.warning(f"Starting openai async fetch. Data Chunk length :{len(data_chunks)}\n")
    try:
        llm_threads = []
        client = AsyncOpenAI(api_key=open_ai_key, max_retries=0)

    except Exception as e:
        log.error(f"Error in async open ai: {e}")
        yield b"[]"

    # Create asyncio tasks for each data chunk with enumeration
    for thread_id, chunk in enumerate(data_chunks):
        task = extract_thread_contacts(thread_id + 1, chunk, prompt, solution, client)
        llm_threads.append(task)

    for completed_task in asyncio.as_completed(llm_threads):
        try:
            result = await completed_task
            result = result["results"] if result != [] else []
            yield result
        except Exception as e:
            log.error(f"Error in task: {e}")

    log.info(f"OpenAI task completed")


async def static_retrieval_multifetching(
    data,
    prompt: str,
    targets: List[str] | None,
    open_ai_key: str,
    context_chunk_size: int = 5,
    max_thread: int = 5,
    timeout: int = 10
) -> list:
    """
    Creates multiple LLM calls
    """
    # Deflate the data for LLM data retrieval
    context_data = [
        { "id": d["metadata"]["id"],"title":d["metadata"]["title"], 
          "content": d["content"]
        }
          for d in data
          ]

    # Divide the data into chunks of size chunk_size
    data_chunks = [
        context_data[i : i + context_chunk_size]
        for i in range(0, len(data), context_chunk_size)
    ]
    data_chunks = data_chunks[:max_thread]
    t_start = time.time()
    log.warning(f"Starting openai async fetch. Data Chunk length :{len(data_chunks)}\n")
    try:
        llm_threads = []
        client = AsyncOpenAI(api_key=open_ai_key, max_retries=0)

        for thread_id, chunk in enumerate(data_chunks):
            task = extract_thread_contacts(
                thread_id + 1, chunk, prompt, targets, client
            )
            llm_threads.append(task)

        results = await asyncio.gather(*llm_threads, return_exceptions=True)
        combined_results = []
        
        for result in results:
            if not result:
                log.warn(f"Unexpected result format: {result}")
                continue
            if result != [] and isinstance(result["results"], list):
                combined_results.extend(result["results"])
            elif isinstance(result, dict) and result != {}:
                combined_results.append(result["results"])
            else:
                log.warn(f"Unexpected result format: {result}")
        t_end = time.time()
        log.info(f"OpenAI task completed")
        log.info(f"\nTotal time taken: {t_end - t_start}; Total results: {len(combined_results)}\n")
        log.info(f"Contacts extracted by OpenAI: {combined_results}")
        
        # inflate the results
        log.info(f" Inflating the results, with the original data")
        inflated_results = inflating_retrieval_results(combined_results, data)

        return inflated_results

    except Exception as e:
        log.error(f"Error in async openai retrival: {e}")
        return []
