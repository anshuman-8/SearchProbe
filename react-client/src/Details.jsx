import React from "react";

export default function Details({ data }) {
  const [feedback, setFeedback] = React.useState("");
  const [rating, setRating] = React.useState();

  const handleFeedbackSubmit = async () => {
    const feedback_response = {
      id: data.id,
      prompt: data.prompt,
      message: feedback,
      rating: Number.parseInt(rating),
      data: data.results,
    };
    try {
      const url = `http://127.0.0.1:8000/feedback`;
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(feedback_response),
      });
      if (response.status === 200) {
        console.log("Feedback submitted successfully");
        setFeedback("");
        setRating("");
        alert("Feedback submitted successfully");
      }
    } catch (err) {
      console.log(err);
    }
  };

  return (
    <div className="my-5">
      {/* {searchSpace}
      {solution} */}
      <h2 className="font-semibold text-lg">Details</h2>
      <div className="flex flex-col justify-start space-y-4 mb-4">
        <div className="flex flex-row space-x-6 justify-start">
          <h3>
            <span className="font-bold">Id:</span> {data.id}
          </h3>
          <h3>
            <span className="font-bold">Time (seconds):</span> {data.meta.time}
          </h3>
          <h3>
            <span className="font-bold">No. of Results:</span> {data.count}
          </h3>
        </div>
        <div className="flex flex-row space-x-6 justify-start">
          <div>
            <span className="font-bold">Search Query:</span>{" "}
            {data.meta.search_query.map((query) => (
              <a
                href={`https://www.google.com/search?q=${query}`}
                className=" mx-1 my-1 bg-slate-100 rounded-md p-1 border hover:border-2 hover:border-blue-400"
                target="_blank"
                rel="noreferrer"
              >
                {query} {"->"}
              </a>
            ))}
          </div>
          <h3>
            <span className="font-bold">Targets:</span> {data.meta.targets.join(", ")}
          </h3>
          {/* <h3>
            <span className="font-bold">Search Space:</span>{" "}
            {data.meta.search_space.join(", ")}
          </h3> */}
        </div>
      </div>
      <h2 className="font-semibold text-lg my-3">Feedback</h2>
      <div className="flex md:flex-row">
        <textarea
          className="border w-full h-24 p-3 max-w-xl md:"
          placeholder="Feedback Message"
          value={feedback}
          rows={2}
          onChange={(e) => setFeedback(e.target.value)}
        />
        <div className="flex flex-col ml-3">
          <input
            className="border px-2 py-4 mt-2 h-10"
            type="number"
            value={rating}
            onChange={(e) => setRating(e.target.value)}
            placeholder="Rating (0-10)"
          />
          <button
            className="border p-2 mt-2 h-10 hover:bg-slate-500 hover:text-white"
            onClick={handleFeedbackSubmit}
          >
            Submit Feedback
          </button>
        </div>
      </div>
    </div>
  );
}
