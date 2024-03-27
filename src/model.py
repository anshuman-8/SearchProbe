import time
import logging as log
from typing import List, Dict
from pydantic import BaseModel

class ContactDetails(BaseModel):
    email: str = ""
    phone: List[str] = []
    address: str = ""


class ServiceProvider(BaseModel):
    service_provider: str
    source: str
    provider: List[str]
    contacts: ContactDetails


class ApiResponse(BaseModel):
    id: str
    status: str
    prompt: str
    location: str
    country: str
    run_time: int
    results: List[ServiceProvider]

class CpAPIResponse(BaseModel):
    questions: List[dict]
    goal_type: str

class CpMergeRequest(BaseModel):
    goal: str
    choices: dict

class ErrorResponseModel(BaseModel):
    id: str
    prompt: str
    status: str = "error"
    message: str

class Feedback(BaseModel):
    id:str
    prompt:str
    message:str
    rating:int
    data: List[dict]



class RequestContext():
    def __init__(self, id:str, prompt:str, location:str, country_code:str):
        self.id = id
        self.prompt = prompt
        self.location = location
        self.country_code = country_code or "US"
        self.start_time = time.time()

        self.contacts = []

        self.targets = []
        self.web_queries = None
        self.yelp_query = None
        self.gmaps_query = None

    def update_search_param(self, search_query:Dict[str, any], targets:List[str]):
        if search_query is None or not isinstance(search_query, dict) or targets is None or not targets:
            log.error(f"No search query or targets provided by Query Generator")
            raise Exception("Search query or Targets not passed")
        
        web_queries = search_query.get("web", None)
        if web_queries is None or not web_queries:
            log.error(f"No web search query provided")
            raise Exception("Web search query not passed")
        elif isinstance(web_queries, str) and web_queries.strip() == "":
            web_queries = [web_queries]

        yelp_query = search_query.get("yelp", None)
        if yelp_query is not None and yelp_query.strip() == "":
            yelp_query = None

        gmaps_query = search_query.get("gmaps", None)
        if gmaps_query is not None and gmaps_query.strip() == "":
            gmaps_query = None

        if isinstance(targets, str) and targets.strip() == "":
            targets = [targets]

        self.targets = targets
        self.web_queries = web_queries
        self.yelp_query = yelp_query
        self.gmaps_query = gmaps_query

    def add_contacts(self, contacts):
        self.contacts.extend(contacts)

