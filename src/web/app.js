(function () {
  const { useEffect, useState } = React;
  const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

  function App() {
    const [file, setFile] = useState(null);
    const [status, setStatus] = useState("");
    const [response, setResponse] = useState(null);
    const [transcript, setTranscript] = useState("");
    const [isUploading, setIsUploading] = useState(false);
    const [isTranscribing, setIsTranscribing] = useState(false);
    const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
    const [view, setView] = useState("upload");
    const [listData, setListData] = useState([]);
    const [listPage, setListPage] = useState(1);
    const [listTotal, setListTotal] = useState(0);
    const [listPageSize, setListPageSize] = useState(10);
    const [isLoadingList, setIsLoadingList] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalSegments, setModalSegments] = useState([]);
    const [modalTitle, setModalTitle] = useState("");

    useEffect(() => {
      let isMounted = true;

      async function loadEnv() {
        try {
          const res = await fetch(`${DEFAULT_API_BASE_URL}/config`);
          if (!res.ok) {
            return;
          }
          const env = await res.json();
          if (isMounted && env.API_BASE_URL) {
            setApiBaseUrl(env.API_BASE_URL);
          }
        } catch (error) {
          if (isMounted) {
            setStatus("Using default API base URL.");
          }
        }
      }

      loadEnv();

      return () => {
        isMounted = false;
      };
    }, []);

    useEffect(() => {
      if (view !== "list") {
        return;
      }
      let isMounted = true;

      async function loadList() {
        try {
          setIsLoadingList(true);
          const res = await fetch(
            `${apiBaseUrl}/transcripts?page=${listPage}&page_size=${listPageSize}`
          );
          if (!res.ok) {
            throw new Error("Failed to load transcripts");
          }
          const payload = await res.json();
          if (isMounted) {
            setListData(payload.items || []);
            setListTotal(payload.total || 0);
            setListPage(payload.page || listPage);
            setListPageSize(payload.page_size || listPageSize);
          }
        } catch (error) {
          if (isMounted) {
            setStatus(error.message || "Failed to load transcripts.");
          }
        } finally {
          if (isMounted) {
            setIsLoadingList(false);
          }
        }
      }

      loadList();

      return () => {
        isMounted = false;
      };
    }, [apiBaseUrl, view, listPage, listPageSize]);

    async function handleSubmit(event) {
      event.preventDefault();
      setResponse(null);
      setTranscript("");

      if (!file) {
        setStatus("Please choose an audio file.");
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        setStatus("Uploading...");
        setIsUploading(true);
        const res = await fetch(`${apiBaseUrl}/upload`, {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const errorPayload = await res.json().catch(() => ({}));
          const detail = errorPayload.detail || "Upload failed";
          throw new Error(detail);
        }

        const payload = await res.json();
        setResponse(payload);
        setStatus("Upload complete.");
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      } finally {
        setIsUploading(false);
      }
    }

    function formatTimestamp(value) {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return "0.00";
      }
      return value.toFixed(2);
    }

    function formatSegments(segments) {
      if (!Array.isArray(segments) || segments.length === 0) {
        return "";
      }
      return segments
        .map((segment) => {
          const text = segment.text || "";
          const timestamp = segment.timestamp || {};
          const start = formatTimestamp(timestamp.start);
          const end = formatTimestamp(timestamp.end);
          return `${start}-${end} : ${text}`.trim();
        })
        .join("\n");
    }

    async function handleTranscribe() {
      if (!response || !response.file_key) {
        setStatus("Upload an audio file before transcribing.");
        return;
      }

      try {
        setStatus("Transcribing...");
        setIsTranscribing(true);
        const res = await fetch(
          `${apiBaseUrl}/transcribe/${response.file_key}`,
          { method: "POST" }
        );

        if (!res.ok) {
          const errorPayload = await res.json().catch(() => ({}));
          const detail = errorPayload.detail || "Transcription failed";
          throw new Error(detail);
        }

        const payload = await res.json();
        const formatted = formatSegments(payload.segments);
        setTranscript(formatted || payload.text || payload.transcript || "");
        setStatus("Transcription complete.");
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      } finally {
        setIsTranscribing(false);
      }
    }

    async function handleViewTranscript(item) {
      try {
        setStatus("");
        const res = await fetch(`${apiBaseUrl}/transcripts/${item.file_key}`);
        if (!res.ok) {
          const errorPayload = await res.json().catch(() => ({}));
          const detail = errorPayload.detail || "Failed to load transcript";
          throw new Error(detail);
        }
        const payload = await res.json();
        setModalSegments(payload.segments || []);
        setModalTitle(item.original_filename || item.file_key);
        setModalOpen(true);
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      }
    }

    function closeModal() {
      setModalOpen(false);
      setModalSegments([]);
      setModalTitle("");
    }

    function formatDuration(value) {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return "—";
      }
      return `${value.toFixed(2)}s`;
    }

    return React.createElement(
      "main",
      { className: "page" },
      React.createElement(
        "div",
        { className: "nav" },
        React.createElement(
          "button",
          {
            type: "button",
            className: view === "upload" ? "secondary" : "ghost",
            onClick: () => setView("upload"),
          },
          "Upload"
        ),
        React.createElement(
          "button",
          {
            type: "button",
            className: view === "list" ? "secondary" : "ghost",
            onClick: () => setView("list"),
          },
          "Recordings"
        )
      ),
      React.createElement(
        "section",
        { className: "card" },
        React.createElement(
          "h1",
          null,
          view === "upload" ? "Audio Upload" : "Recordings"
        ),
        React.createElement(
          "p",
          { className: "subtitle" },
          view === "upload"
            ? "Send an audio file to the FastAPI /upload endpoint."
            : "Browse recordings that have been transcribed."
        ),
        view === "upload"
          ? React.createElement(
              React.Fragment,
              null,
              React.createElement(
                "form",
                { onSubmit: handleSubmit, className: "form" },
                React.createElement("input", {
                  type: "file",
                  accept: "audio/*",
                  onChange: (event) => setFile(event.target.files[0] || null),
                }),
                React.createElement(
                  "button",
                  { type: "submit", disabled: isUploading },
                  isUploading ? "Uploading..." : "Upload"
                )
              ),
              React.createElement(
                "div",
                { className: "actions" },
                React.createElement(
                  "button",
                  {
                    type: "button",
                    onClick: handleTranscribe,
                    disabled: !response || isTranscribing,
                    className: "secondary",
                  },
                  isTranscribing ? "Transcribing..." : "Transcribe"
                )
              )
            )
          : React.createElement(
              "div",
              { className: "list" },
              isLoadingList
                ? React.createElement(
                    "div",
                    { className: "status" },
                    "Loading recordings..."
                  )
                : null,
              React.createElement(
                "table",
                { className: "table" },
                React.createElement(
                  "thead",
                  null,
                  React.createElement(
                    "tr",
                    null,
                    React.createElement("th", null, "File name"),
                    React.createElement("th", null, "Type"),
                    React.createElement("th", null, "Duration"),
                    React.createElement("th", null, "Transcript"),
                    React.createElement("th", null, "Actions")
                  )
                ),
                React.createElement(
                  "tbody",
                  null,
                  listData.length
                    ? listData.map((item) =>
                        React.createElement(
                          "tr",
                          { key: item.file_key },
                          React.createElement(
                            "td",
                            null,
                            item.original_filename || item.file_key
                          ),
                          React.createElement(
                            "td",
                            null,
                            item.content_type || "—"
                          ),
                          React.createElement(
                            "td",
                            null,
                            formatDuration(item.duration_seconds)
                          ),
                          React.createElement(
                            "td",
                            null,
                            item.transcript_available ? "Yes" : "No"
                          ),
                          React.createElement(
                            "td",
                            null,
                            item.transcript_available
                              ? React.createElement(
                                  "button",
                                  {
                                    type: "button",
                                    className: "ghost",
                                    onClick: () => handleViewTranscript(item),
                                  },
                                  "View"
                                )
                              : "—"
                          )
                        )
                      )
                    : React.createElement(
                        "tr",
                        null,
                        React.createElement(
                          "td",
                          { colSpan: 5 },
                          "No transcripts available yet."
                        )
                      )
                )
              ),
              React.createElement(
                "div",
                { className: "pagination" },
                React.createElement(
                  "button",
                  {
                    type: "button",
                    className: "ghost",
                    disabled: listPage <= 1 || isLoadingList,
                    onClick: () => setListPage(Math.max(1, listPage - 1)),
                  },
                  "Prev"
                ),
                React.createElement(
                  "span",
                  { className: "page-meta" },
                  `Page ${listPage} of ${Math.max(
                    1,
                    Math.ceil(listTotal / listPageSize)
                  )}`
                ),
                React.createElement(
                  "button",
                  {
                    type: "button",
                    className: "ghost",
                    disabled:
                      listPage >= Math.ceil(listTotal / listPageSize) ||
                      isLoadingList,
                    onClick: () =>
                      setListPage(
                        Math.min(
                          Math.ceil(listTotal / listPageSize) || 1,
                          listPage + 1
                        )
                      ),
                  },
                  "Next"
                )
              )
            ),
        status
          ? React.createElement(
              "div",
              { className: "status" },
              status
            )
          : null,
        view === "upload" && response
          ? React.createElement(
              "pre",
              { className: "response" },
              JSON.stringify(response, null, 2)
            )
          : null,
        view === "upload"
          ? React.createElement(
              "div",
              { className: "transcript" },
              React.createElement(
                "label",
                { htmlFor: "transcript-box" },
                "Transcript"
              ),
              React.createElement("textarea", {
                id: "transcript-box",
                placeholder: "Transcript will appear here after processing.",
                value: transcript,
                readOnly: true,
              })
            )
          : null,
        modalOpen
          ? React.createElement(
              "div",
              { className: "modal-backdrop", onClick: closeModal },
              React.createElement(
                "div",
                {
                  className: "modal",
                  onClick: (event) => event.stopPropagation(),
                },
                React.createElement(
                  "div",
                  { className: "modal-header" },
                  React.createElement("h2", null, modalTitle || "Transcript"),
                  React.createElement(
                    "button",
                    { type: "button", className: "ghost", onClick: closeModal },
                    "Close"
                  )
                ),
                React.createElement(
                  "div",
                  { className: "modal-body" },
                  React.createElement(
                    "pre",
                    { className: "modal-content" },
                    formatSegments(modalSegments)
                  )
                )
              )
            )
          : null
      )
    );
  }

  const root = ReactDOM.createRoot(document.getElementById("root"));
  root.render(React.createElement(App));
})();
