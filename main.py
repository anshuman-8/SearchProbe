import uuid
import time
import json
import logging as log
from typing import List
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response
from src.app import (
    search_query_extrapolate,
    extract_web_context,
    response_formatter,
    stream_contacts_retrieval,
    static_contacts_retrieval,
)
from src.model import ApiResponse, ErrorResponseModel, RequestContext, Feedback, CpAPIResponse, CpMergeRequest
from src.copilot.question_generation import generate_question
from src.copilot.query_merge import merge_goal
from src.lmBasic.titleGenerator import generate_title
import tracemalloc

tracemalloc.start()

app = FastAPI(title="Margati Probe", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    response = {
        "status_code": 200,
        "message": "Hello World",
        "status": "ok",
        "data": None,
    }
    return response


async def stream_response(request_context: RequestContext, data: List[dict]):
    async for chunk in stream_contacts_retrieval(request_context, data):
        end_time = time.time()
        request_context.add_contacts(chunk)
        response = await response_formatter(
            request_context.id,
            (end_time - request_context.start_time),
            request_context.prompt,
            request_context.location,
            chunk,
            request_context.solution,
            request_context.search_space,
            request_context.search_query,
        )
        log.info(f"\nStreaming Response: {response}")
        yield response

    final_response = await response_formatter(
        request_context.id,
        (end_time - request_context.start_time),
        request_context.prompt,
        request_context.location,
        request_context.contacts,
        request_context.solution,
        request_context.search_space,
        request_context.search_query,
        status="completed",
        has_more=False,
    )
    log.info(f"\nStreaming Final Response: {final_response}")

    date = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
    with open(f"response-logs/{date}.json", "w") as f:
        f.write(str(final_response))

    yield final_response


async def static_response(request_context: RequestContext, data: List[dict]):
    results = await static_contacts_retrieval(request_context, data, full_search=False)
    end_time = time.time()
    response = await response_formatter(
        request_context.id,
        (end_time - request_context.start_time),
        request_context.prompt,
        request_context.location,
        results,
        request_context.solution,
        request_context.search_space,
        request_context.search_query,
        status="completed",
        has_more=False,
    )

    log.info(f"\nStatic Response: {response}")
    date = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
    with open(f"response-logs/{date}.json", "w") as f:
        f.write(str(response))
    return response

def collect_data(id, goal, solution, context, search_space, search_query, results): 
    data = {
        "id": id,
        "goal": goal,
        "solution": solution,
        "context": context,
        "search_space": search_space,
        "search_query": search_query,
        "results": json.loads(results)
    }
    log.info(f"\nData collected for {id} in data-collection!\n")
    with open(f"data-collection/{id}.json", "w") as f:
        json.dump(data, f)


@app.get("/q/")
async def probe(
    request: Request,
    prompt: str | None = "",
    location: str | None = "",
    country_code: str | None = "US",
) -> ApiResponse | ErrorResponseModel:
    ID = uuid.uuid4()
    timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
    print(ID)

    log.basicConfig(
        filename=f"logs/{ID}.log",
        filemode="w",
        format="%(name)s - %(levelname)s - %(message)s",
        level=log.INFO,
    )

    if prompt is None or not prompt.strip():
        log.error(f"No prompt provided")
        raise HTTPException(status_code=400, detail="prompt needed!")
    if location is None or not location.strip():
        log.error(f"Location not provided")
        raise HTTPException(status_code=400, detail="location needed!")

    request_context = RequestContext(str(ID), prompt, location, country_code)

    log.info(f"Request: {prompt}, {location}, {country_code}")
    log.info(f"Request from: {request.client.host}")
    log.info(f"Total Time: {timestamp}")

    try:
        query, solution, search_space = search_query_extrapolate(
            request_context=request_context,
        )
        request_context.update_search_param(query, solution, search_space)

        web_context = await extract_web_context(request_context=request_context)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"id": str(ID), "status": "Internal Error", "message": str(e)},
        )

    return StreamingResponse(content=stream_response(request_context, web_context))


@app.get("/static/")
async def staticProbe(
    request: Request,
    prompt: str | None = "",
    location: str | None = "",
    country_code: str | None = "US",
) -> ApiResponse | ErrorResponseModel:
    ID = uuid.uuid4()
    timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

    log.basicConfig(
        filename=f"logs/{ID}.log",
        filemode="w",
        format="%(name)s - %(levelname)s - %(message)s",
        level=log.INFO,
    )
    print(f'logs/{ID}.log')

    if prompt is None or not prompt.strip():
        log.error(f"No prompt provided")
        raise HTTPException(status_code=400, detail="prompt needed!")
    if location is None or not location.strip():
        log.error(f"Location not provided")
        raise HTTPException(status_code=400, detail="location needed!")

    request_context = RequestContext(str(ID), prompt, location, country_code)

    log.info(f"Request: {prompt}, {location}, {country_code}")
    log.info(f"Request from: {request.client.host}")
    log.info(f"Total Time: {timestamp}")

    try:
        query, solution, keyword, search_space = search_query_extrapolate(
            request_context=request_context,
        )
        request_context.update_search_param(query, solution, keyword, search_space)

        web_context = await extract_web_context(request_context=request_context, deep_scrape=True)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"id": str(ID), "status": "Internal Error", "message": str(e)},
        )
    
    response = await static_response(request_context, web_context)

    # collect_data(str(ID), prompt, solution, web_context, search_space, query, response)
    
    return Response(content=response)

@app.get("/title/")
async def title(
    request: Request,
    goal: str | None,
) -> JSONResponse:
    ID = uuid.uuid4()
    timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

    log.basicConfig(
        filename=f"logs/title-{ID}.log",
        filemode="w",
        format="%(name)s - %(levelname)s - %(message)s",
        level=log.INFO,
    )

    if goal is None or not goal.strip():
        log.error(f"No goal provided")
        raise HTTPException(status_code=400, detail="goal needed!")

    try:
        response = generate_title(goal)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={ "status": "Internal Error", "message": str(e)},
        )

    return JSONResponse(content=response)

@app.get("/copilot/")
async def copilot(
    request: Request,
    prompt: str | None, 
    location: str | None,
) -> CpAPIResponse | ErrorResponseModel:
    ID = uuid.uuid4()
    timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
    
    log.basicConfig(
        filename=f"logs/cp-{ID}.log",
        filemode="w",
        format="%(name)s - %(levelname)s - %(message)s",
        level=log.INFO,
    )

    if prompt is None or not prompt.strip():
        log.error(f"No prompt provided")
        raise HTTPException(status_code=400, detail="prompt needed!")
    
    try:
        response = generate_question(prompt, location)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={ "status": "Internal Error", "message": str(e)},
        )

    return JSONResponse(content=response)


@app.post("/copilot/merge/")
def cpMerge(
    request: CpMergeRequest 
) -> CpAPIResponse | ErrorResponseModel:
    
    try:
        response = merge_goal(request.choices, request.goal)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={ "status": "Internal Error", "message": str(e)},
        )
    return JSONResponse(response)

@app.post("/feedback/")
async def feedback(request: Request, feedback: Feedback) -> JSONResponse:
    date = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

    feedback_data = {
        "request_id": feedback.id,
        "feedback": feedback.message,
        "rating": feedback.rating,
        "prompt": feedback.prompt,
        "user_ip": request.client.host,
        "user_agent": request.headers["user-agent"],
        "timestamp": date,
        "data": feedback.data,
    }

    with open(f"feedbacks/{date}_{feedback.id}.json", "w") as f:
        json.dump(feedback_data, f)

    return JSONResponse(
        content={
            "status": "ok",
            "message": "Feedback received",
        },
        status_code=200,
    )
