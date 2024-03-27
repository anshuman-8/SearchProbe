from langchain.docstore.document import Document
import logging as log
import json
import random
from typing import List, Optional
import copy
import re


def create_documents(
    texts: List[str], metadatas: Optional[List[dict]] = None
) -> List[Document]:
    """Create documents from a list of texts."""
    _metadatas = metadatas or [{}] * len(texts)
    documents = []
    for i, text in enumerate(texts):
        metadata = copy.deepcopy(_metadatas[i])
        new_doc = Document(page_content=text, metadata=metadata)
        documents.append(new_doc)
    return documents


def document_lambda(
    documents: List[Document], func: callable
) -> List[Document]:
    """Filter documents based on a regex pattern.
    ### Parameters:
    - documents: List of documents to be filtered.
    - lambda : lambda function to be applied on the documents

    ### Returns:
    List of documents after running the lambda function on them.
    """
    texts, metadatas = [], []
    for doc in documents:
        texts.append(doc.page_content)
        metadatas.append(doc.metadata)
    texts = [func(text) for text in texts]
    return create_documents(texts, metadatas=metadatas)


def document2map(documents: List[Document]) -> List[dict]:
    """Convert a list of documents to a map."""
    log.info("Converting documents to map...")
    return [
        {"metadata": doc.metadata, "content": doc.page_content} for doc in documents
    ]

def rank_weblinks(web_links: List[dict]) -> List[dict]:
    """
    Ranks the web links by adding rank field and making the list unique
    """
    # make the list unique
    unique_web_links = []
    for web_link in web_links:
        if web_link not in unique_web_links:
            unique_web_links.append(web_link)

    # add rank field
    for i, web_link in enumerate(unique_web_links):
        web_link["rank"] = i + 1
        web_link["id"] = i 

    return unique_web_links

def inflating_retrieval_results(results: List[dict], base_informationList: List[dict]) -> List[dict]:
    """
    Inflating the retrieval results with the base information
    """
    inflated_results = []
    base_info_dict = {info.get("metadata", {}).get("id"): info for info in base_informationList}

    for result in results:
        id = result.get("id")
        if id is None:
            continue

        base_info = base_info_dict.get(id)
        if base_info is None:
            continue

        base_info.pop("content", None)
        base_info["metadata"].pop("title", None)
        base_info["metadata"].pop("id", None)
        result = {**result, **base_info}
        inflated_results.append(result)

    return inflated_results

def gpt_cost_calculator(
    inp_tokens: int, out_tokens: int, model: str = "gpt-3.5-turbo"
) -> int:
    """
    Calculate the cost of the GPT API call

    Model List:
    - gpt-4
    - gpt-3.5-turbo
    - gpt-4-turbo-1106
    - gpt-3.5-turbo-finetune
    """
    cost = 0
    # GPT-3.5 Turbo
    if model == "gpt-3.5-turbo":
        input_cost = 0.5
        output_cost = 1.5
        cost = ((inp_tokens * input_cost) + (out_tokens * output_cost)) / 1000000
    elif model == "gpt-3.5-turbo-finetune":
        input_cost = 3.0
        output_cost = 6.0
        cost = ((inp_tokens * input_cost) + (out_tokens * output_cost)) / 1000000
    elif model == "gpt-4-turbo-1106":
        input_cost = 10.0
        output_cost = 30.0
        cost = ((inp_tokens * input_cost) + (out_tokens * output_cost)) / 1000000
    # GPT-4
    elif model == "gpt-4":
        input_cost = 30.00
        output_cost = 60.00
        cost = ((inp_tokens * input_cost) + (out_tokens * output_cost)) / 1000000
    else:
        log.error("Invalid model")

    return cost

def sort_results(results: List[dict]) -> List[dict]:
    """
    Sort the results based on the rank
    """
    sorted_list = sorted(results, key=lambda x: x['rank'])

    results = []
    # Reassign the ranks as 1, 2, 3, ...
    for index, item in enumerate(sorted_list, start=1):
        updated_item = dict(item)
        updated_item['rank'] = index
        results.append(updated_item)

    return results


def process_results(results):
    log.debug(f"Processing API results : {results}")
    # Initialize an empty list to store processed results
    processed_results = []

    try:
        for result in results:
            if isinstance(result, (str)):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        result = {}
            
            if isinstance(result, dict):
                contacts = result.get("contacts", {})
                email = ""
                phone = ""
                if contacts.get("email"):
                    if isinstance(contacts["email"], list):
                        email = re.search(
                            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                            contacts["email"][0],
                        )
                    else:
                        email = re.search(
                            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                            contacts["email"],
                        )

                if contacts.get("phone"):
                    if isinstance(contacts["phone"], list):
                        phone = re.search(
                            r'\b(?:\+\d{1,3}\s?)?(?:\(\d{1,4}\)|\d{1,4})[\s.-]?\d{3,9}[\s.-]?\d{4}\b',
                            contacts["phone"][0],
                        )
                    else:
                        phone = re.search(
                            r'\b(?:\+\d{1,3}\s?)?(?:\(\d{1,4}\)|\d{1,4})[\s.-]?\d{3,9}[\s.-]?\d{4}\b',
                            contacts["phone"],
                        )

                processed_result = {
                    "id": result.get("id", random.randint(30, 60)),
                    "rank": result.get("metadata",{}).get("rank"),
                    "name": result.get("name", ""),
                    "target": result.get("target", ""),
                    "source": result.get("metadata",{}).get("link", ""),
                    "info": result.get("info",""),
                    "provider": result.get("metadata",{}).get("source", []),
                    "latitude": result.get("metadata",{}).get("latitude", None),
                    "longitude": result.get("metadata",{}).get("longitude", None),
                    "rating": result.get("metadata",{}).get("rating", ""),
                    "rating_count": result.get("metadata",{}).get("rating_count", ""),
                    "contacts": {
                        "email": email.string if email else "",
                        "phone": phone.string if phone else "",
                        "address": contacts.get("address", ""),
                    },
                }
                if (
                    processed_result["contacts"]["email"].strip() == ""
                    and processed_result["contacts"]["phone"].strip() == ""
                    and processed_result["contacts"]["address"].strip() == ""
                ):
                    continue

                # Append the processed result to the list
                processed_results.append(processed_result)
        
        # sorting
        processed_results = sort_results(processed_results)

    except Exception as e:
        log.error(f"Error processing API results : {e}")
        raise Exception("Error processing API results")
    
    return processed_results


def merge_response(car_rental_list):
    merged_services = {}

    for service in car_rental_list:
        phone = (
            service["contacts"]["phone"][0] if service["contacts"]["phone"] else None
        )
        name = service["name"]
        provider = service["provider"][0] if service["provider"] else None

        if phone not in merged_services:
            merged_services[phone] = {
                "name": name,
                "source": service["source"],
                "provider": [provider] if provider else [],
            }
        else:
            if provider and provider not in merged_services[phone]["provider"]:
                merged_services[phone]["provider"].append(provider)

    # Convert merged_services dictionary back to list of dictionaries
    merged_list = [
        {
            "name": value["name"],
            "source": value["source"],
            "provider": value["provider"],
            "contacts": {
                "phone": [phone],
                "email": [],  # You can add email merging logic if needed
                "address": "",  # You can add address merging logic if needed
            },
        }
        for phone, value in merged_services.items()
    ]

    return merged_list
