import os
import json
import time
import logging as log
from typing import List
from dotenv import load_dotenv

from src.sanitize_query import generate_search_query
from src.webScraper import scrape_with_playwright
from src.data_preprocessing import process_data_docs
from src.contactRetrieval import (
    retrieval_multithreading,
    static_retrieval_multifetching,
)
from src.search import Search
from src.model import RequestContext
from src.utils import process_results, rank_weblinks, sort_results

load_dotenv()

OPENAI_ENV = os.getenv("OPENAI_API_KEY")


def process_search_results(results: List[str]) -> List[str]:
    """
    Process the search links to remove the unwanted links
    """
    avoid_links = [
        "instagram",
        "facebook",
        "twitter",
        "youtube",
        "makemytrip",
        "linkedin",
        "justdial",
        "indeed",
        "reddit",
        "yelp",
    ]
    processed_results = []
    for result in results:
        if not any(avoid_link in result["link"] for avoid_link in avoid_links):
            processed_results.append(result)
    return processed_results


def search_query_extrapolate(request_context: RequestContext):
    """
    Extract the search query from the prompt

    Returns : search query and goal target 
    """
    log.info(f"Prompt: {request_context.prompt}")
    goal_target = []
    try:
        goal_query = generate_search_query(
            request_context.prompt,
            location=request_context.location,
            open_api_key=OPENAI_ENV,
        )
        search_query = goal_query["queries"]
        goal_target = goal_query["targets"]

    except Exception as e:
        log.error(f"Prompt sanitization failed, Error:{e}")
        raise Exception("Prompt sanitization failed")

    return (search_query, goal_target)


async def extract_web_context(request_context: RequestContext, deep_scrape: bool = False):
    """
    Extract the web context from the search results

    ### Response
    List[dict] - 
    {
        "id": str,
        "rank": int,
        "title": str,
        "link": str,
        "content": str,
        "source": str,
        "meta": dict
    }
    """
    search_client = Search(
        web_queries=request_context.web_queries,
        yelp_query=request_context.yelp_query,
        gmaps_query=request_context.gmaps_query,
        location=request_context.location,
        country_code=request_context.country_code,
        timeout=15,
        yelp_search=False,
    )

    max_web_results = 30
    if request_context.gmaps_query is not None or request_context.yelp_query is not None:
        max_web_results = 25

    # get the search results
    web_results = await search_client.search_web(max_results=max_web_results)

    # process the search links
    search_results = process_search_results(web_results[:max_web_results])
    log.info(f"\nRefined Search Results length: {len(search_results)}\n")

    if deep_scrape and (request_context.gmaps_query is not None):
        response_gmaps = await search_client.search_google_business()
        if response_gmaps is not None:
            gmaps_links = search_client.process_google_business_links(
                response_gmaps
            )
            gmaps_links = gmaps_links[:25]
            log.debug(f"\nGoogle Business Details: {gmaps_links}\n")
            search_results = gmaps_links + search_results
        else:
            log.warning("Google Business data not used")
    # ranking and filtering
    refined_search_results = rank_weblinks(search_results)

    # scrape the websites
    extracted_content = await scrape_with_playwright(refined_search_results)
    log.info(f"\nScraped Content: {len(extracted_content)}\n")

    if len(extracted_content) == 0:
        log.error("No content extracted")
        raise Exception("No web content extracted!")

    # Preprocess the extracted content
    context_data, site_contact_links = process_data_docs(extracted_content, 550)
    log.info(f"\nContext Data len: {len(context_data)}\n")

    if len(site_contact_links) > 0:
        secondary_context_data = await secondary_search(site_contact_links)
        context_data.extend(secondary_context_data)
        log.info(f"\nTotal Context Data len: {len(context_data)}\n")
    else:
        log.warning("No secondary search required\n")

    data = [x for x in context_data if len(x["content"]) > 400]

    if len(data) == 0:
        log.error("No relevant data extracted")
        return []
    
    return data


async def secondary_search(web_links:List[str]):
    extracted_content = await scrape_with_playwright(web_links)
    log.info(f"\nSecondary Scraped Content: {len(extracted_content)}\n")

    if len(extracted_content) == 0:
        log.error("No content extracted")
        raise Exception("No web content extracted!")

    # Preprocess the extracted content
    context_data, site_contact_links = process_data_docs(extracted_content, 450)
    log.info(f"\nSecondary Context Data len: {len(context_data)}\n")
    
    return context_data


async def static_contacts_retrieval(
    request_context: RequestContext, data, context_chunk_size: int = 5
) -> List[dict]:
    """
    Extract the contacts from the search results using LLM
    """

    # OpenAI response
    web_result = await static_retrieval_multifetching(
        data,
        request_context.prompt,
        request_context.targets,
        OPENAI_ENV,
        context_chunk_size=5,
        max_thread=10,
        timeout=10,
    )

    end_time = time.time()

    response = await response_formatter(
        request_context.id,
        (end_time - request_context.start_time),
        request_context.prompt,
        request_context.location,
        web_result,
        request_context.targets,
        request_context.web_queries,
        has_more=False,
    )

    log.info(f"\nStatic Response: {response}")
    date = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
    with open(f"response-logs/{date}.json", "w") as f:
        f.write(str(response))

    return response


async def response_formatter(
    id: str,
    time,
    prompt: str,
    location: str,
    results,
    targets: List[str],
    search_query: str,
    has_more: bool = True,
):
    """
    Format the response for the API
    """
    results = process_results(results)
    meta = {
        "targets": targets,
        "search_query": search_query,
        "time": int(time),
    }
    response = {
        "id": str(id),
        "location": str(location),
        "prompt": str(prompt),
        "count": len(results),
        "results": results,
        "meta": meta,
    }

    # convert to json
    json_response = json.dumps(response)

    return json_response
