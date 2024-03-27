import React from "react";

export default function Card({ vendor }) {
  const { name, contacts, source, provider, target } = vendor;

  return (
    <div className="border p-4 rounded-md shadow-md hover:shadow-xl">
      <h2 className="text-xl font-semibold">{name}</h2>
      <div className="text-base text-slate-400 px-1">{target}</div>
      {vendor.info && <p className="text-gray-600">{vendor.info}</p>}

      {
        vendor.latitude && vendor.longitude && (
          <a className="mt-4 border rounded-md p-1 mx-1 my-2 bg-gray-200 hover:shadow-md" href={`https://maps.google.com/?q=${vendor.latitude},${vendor.longitude}`}>
            {"Location ->"}
          </a>
        )
      }
      {
        vendor.rating && (
          <div className="mt-4">
            <strong>Rating:</strong>
            <span className="px-2">{vendor.rating} <span className="text-slate-500">({vendor.rating_count})</span></span>
          </div>
        )
      }


      <div className="mt-4">
        <strong>Contact Information:</strong>
        <p>
          Email:{" "}
          {contacts.email instanceof Array
            ? contacts.email.join(", ")
            : contacts.email}
        </p>
        <p>
          Phone:{" "}
          {contacts.phone instanceof Array
            ? contacts.phone.join(", ")
            : contacts.phone}
        </p>
        <p>Address: {contacts.address}</p>
      </div>

      <div className="mt-4">
        <strong>Additional Information:</strong>
        <p>
          Source:{" "}
          <a
            href={source}
            target="_blank"
            rel="noopener noreferrer"
            className="overflow-auto truncate block max-w-full text-blue-500"
          >
            {source}
          </a>
        </p>
        <p>Provider: {provider.join(", ")}</p>
      </div>
    </div>
  );
}
