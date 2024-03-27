import json
import re
import time
import logging as log
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString, Tag
from typing import Dict, Any, Iterator, List, Sequence, cast, Tuple
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.utils import create_documents, document_lambda, document2map


LOG_FILES = False

def transform_documents(
        documents: Sequence[Document],
        unwanted_tags: List[str] = ["script", "style"],
        tags_to_extract: List[str] = ["p", "li", "div", "a"],
        remove_lines: bool = True,
    ) -> Sequence[Document]:
        site_contact_links = []
        for doc in documents:
            cleaned_content = doc.page_content

            cleaned_content = remove_unwanted_tags(cleaned_content, unwanted_tags)
            cleaned_content, contact_href = extract_tags(cleaned_content, tags_to_extract)

            site_contact_link = combine_contactlink(doc.metadata,contact_href) 
            
            if site_contact_link:
                site_contact_links.append(site_contact_link)
            
            if remove_lines:
                cleaned_content = remove_unnecessary_lines(cleaned_content)

            doc.page_content = cleaned_content

        return documents, site_contact_links

def combine_contactlink(base_link:dict, contact_link:List[str]) -> dict | None:
    if len(contact_link) < 1:
        return None
    single_contact_link = contact_link[0]
    try:
        combined_link_dict = base_link.copy()
        combined_link_dict["base_link"] = base_link["link"]
        if single_contact_link.startswith("href"):
            combined_link_dict["link"] = single_contact_link
            return combined_link_dict
        else:
            base_domain = f"{urlparse(base_link["link"]).scheme}://{urlparse(base_link["link"]).hostname}"
            combined_link = urljoin(base_domain, single_contact_link)
            combined_link_dict["link"] = combined_link
            return combined_link_dict
    except Exception as e:
        log.warn(f"Error combining link: {e}")
        return None

def remove_unwanted_tags(html_content: str, unwanted_tags: List[str]) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in unwanted_tags:
        for element in soup.find_all(tag):
            element.decompose()
    return str(soup)

def extract_tags(html_content: str, tags: List[str]) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    text_parts: List[str] = []
    contact_hrefs: List[str] = []
    for element in soup.find_all():
        if element.name in tags:
            navigable_text, contact_href = get_navigable_strings(element)
            text_parts += navigable_text
            contact_hrefs += contact_href
            element.decompose()

    return " ".join(text_parts), contact_hrefs

def remove_unnecessary_lines(content: str) -> str:
    lines = content.split("\n")
    stripped_lines = [line.strip() for line in lines]
    non_empty_lines = [line for line in stripped_lines if line]
    cleaned_content = " ".join(non_empty_lines)
    return cleaned_content

def get_navigable_strings(element: Any) -> Tuple[List[str], List[str]]:
    text_parts = []
    contact_hrefs = []

    for child in cast(Tag, element).children:
        if isinstance(child, Tag):
            child_text, child_contact_hrefs = get_navigable_strings(child)
            text_parts.extend(child_text)
            contact_hrefs.extend(child_contact_hrefs)
        elif isinstance(child, NavigableString):
            if (element.name == "a") and (href := element.get("href")):
                if href.startswith(("mailto:", "tel:")):
                    text_parts.append(f"{child.strip()} [Contact:({href})]")
                elif "contact" in href.lower():
                    contact_hrefs.append(href)
            else:
                text_parts.append(child.strip())

    return text_parts, contact_hrefs
            
def preprocess_text(docs: Document) -> Dict:
    """
    Extract text from HTML and preprocess it using BeautifulSoup
    """
    t_flag1 = time.time()

    # Beautiful Soup Transformer
    docs_transformed, site_contact_links = transform_documents(
        docs,
        tags_to_extract=["p", "li", "div", "a", "span", "tr", "article"],
        unwanted_tags=["script", "style", "noscript", "svg", "img", "input", "pre", "template"],
    )
    # remove long white space
    regex_lambda = lambda x: re.sub(r"\s+", " ", x) 
    docs_transformed = document_lambda(docs_transformed, func=regex_lambda)

    unicode_lambda = lambda x: x.encode('utf-8', errors='ignore').decode('utf-8')
    docs_transformed = document_lambda(docs_transformed, func=unicode_lambda)
    
    t_flag2 = time.time()
    log.info(f"BeautifulSoupTransformer time: {t_flag2 - t_flag1}")

    if LOG_FILES:
        with open("src/log_data/docs_beautify.json", "w") as f:
            json.dump(document2map(docs_transformed), f)

    return docs_transformed, site_contact_links


def docs_recursive_split(docs: Document, chunk_size: int = 400, overlap:int=50) -> List[Document]:
    """
    Split the documents into chunks using RecursiveCharacterTextSplitter
    """
    t_flag1 = time.time()
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size, chunk_overlap=overlap
    )
    splits = splitter.split_documents(docs)

    t_flag2 = time.time()
    log.info(f"RecursiveCharacterTextSplitter time: {t_flag2 - t_flag1}")

    # convert to dictoinary
    splits = document2map(splits)

    if LOG_FILES:
        with open("src/log_data/splits.json", "w") as f:
            json.dump(splits, f)

    log.info(f"Total data splits: {len(splits)}")
    return splits


def contains_contacts(text: str, email_only:bool=False) -> bool:
    """
    Check if the text contains email or phone number
    """
    # Regular expression patterns for emails and phone numbers
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    phone_pattern = r"\b(?:\+\d{1,3}\s?)?(?:\(\d{1,4}\)|\d{1,4})[\s.-]?\d{3,9}[\s.-]?\d{4}\b|\b\d{10}\b"

    contains_email = bool(re.search(email_pattern, text))
    contains_phone = bool(re.search(phone_pattern, text)) if not email_only else False

    return contains_email or contains_phone


def relevant_data(extracted_content):
    """
    Extract relevant data(checking for email and phone number) from the search results
    """
    t_flag1 = time.time()
    log.debug(f"before extraction: {len(extracted_content)}")
    data = [chunk for chunk in extracted_content if contains_contacts(chunk["content"], email_only=True)]
    log.debug(f"after extraction: {len(data)}")
    t_flag2 = time.time()
    log.info(f"Extraction time: {t_flag2 - t_flag1}")

    if LOG_FILES:
        with open("src/log_data/context_data.json", "w") as f:
            json.dump(data, f)

    return data


def process_secondary_links(base_data, site_contact_links):
    """
    """
    base_links = [chunk["metadata"]["link"] for chunk in base_data]

    new_site_contact_link = {}
    for link in site_contact_links:
        if (link["base_link"] not in base_links) and (link["link"] not in new_site_contact_link.keys()):
            new_site_contact_link[link["link"]] = link

    new_site_contact_link = list(new_site_contact_link.values())
    return new_site_contact_link


def process_data_docs(html_docs: Document, chunk_size: int = 400):
    """
    Process the data by extracting text from HTML, splitting it into chunks and extracting relevant data.
    Also gives list of secondary search links
    """
    html_docs = list(filter(lambda doc: contains_contacts(doc.page_content, email_only=True), html_docs))
    log.warn(f"Length after doc regex processing: {len(html_docs)}")

    docs, site_contact_links = preprocess_text(docs=html_docs)

    data = docs_recursive_split(docs=docs, chunk_size=chunk_size, overlap=15)

    data = relevant_data(extracted_content=data)

    sec_site_contact_links = process_secondary_links(data, site_contact_links)

    return data, sec_site_contact_links
