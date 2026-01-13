(function () {
  const { useEffect, useState } = React;
  const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

  function App() {
    const [file, setFile] = useState(null);
    const [status, setStatus] = useState("");
    const [response, setResponse] = useState(null);
    const [sessionId, setSessionId] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isProcessingLarge, setIsProcessingLarge] = useState(false);
    const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
    const [view, setView] = useState("upload");
    const [listData, setListData] = useState([]);
    const [listPage, setListPage] = useState(1);
    const [listTotal, setListTotal] = useState(0);
    const [listPageSize, setListPageSize] = useState(10);
    const [isLoadingList, setIsLoadingList] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalContent, setModalContent] = useState(null);
    const [modalTitle, setModalTitle] = useState("");
    const [modalType, setModalType] = useState("notes");
    const [openMenuSessionId, setOpenMenuSessionId] = useState(null);
    const [theme, setTheme] = useState("light");

    useEffect(() => {
      let isMounted = true;
      const storedTheme = localStorage.getItem("theme");
      if (storedTheme === "dark" || storedTheme === "light") {
        setTheme(storedTheme);
      }

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
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
    }, [theme]);

    useEffect(() => {
      if (view !== "list") {
        return;
      }
      let isMounted = true;

      async function loadList() {
        try {
          setIsLoadingList(true);
          const res = await fetch(
            `${apiBaseUrl}/sessions?page=${listPage}&page_size=${listPageSize}`
          );
          if (!res.ok) {
            throw new Error("Failed to load sessions");
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
            setStatus(error.message || "Failed to load sessions.");
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
      setSessionId(null);

      if (!file) {
        setStatus("Please choose an audio file.");
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        setStatus("Uploading...");
        setIsUploading(true);
        const res = await fetch(`${apiBaseUrl}/sessions/upload`, {
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
        setSessionId(payload.session_id || null);
        setStatus("Upload complete.");
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      } finally {
        setIsUploading(false);
      }
    }

    async function handleProcessLarge() {
      if (!sessionId) {
        setStatus("Upload a session recording before processing.");
        return;
      }

      try {
        setStatus("Queueing chunked processing...");
        setIsProcessingLarge(true);
        const res = await fetch(
          `${apiBaseUrl}/sessions/${sessionId}/process-large`,
          { method: "POST" }
        );
        if (!res.ok) {
          const errorPayload = await res.json().catch(() => ({}));
          const detail = errorPayload.detail || "Chunked processing failed";
          throw new Error(detail);
        }
        setStatus("Chunked processing started in the background.");
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      } finally {
        setIsProcessingLarge(false);
      }
    }

    async function handleViewNotes(item) {
      try {
        setStatus("");
        const res = await fetch(`${apiBaseUrl}/sessions/${item.session_id}/notes`);
        if (!res.ok) {
          const errorPayload = await res.json().catch(() => ({}));
          const detail = errorPayload.detail || "Failed to load notes";
          throw new Error(detail);
        }
        const payload = await res.json();
        setModalContent(payload.note_markdown || "");
        setModalType("notes");
        setModalTitle(item.title || "Session Notes");
        setModalOpen(true);
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      }
    }

    function formatTimecode(value) {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return "00:00.00";
      }
      const safeValue = Math.max(0, value);
      const minutes = Math.floor(safeValue / 60);
      const seconds = safeValue - minutes * 60;
      const minutesText = String(minutes).padStart(2, "0");
      const secondsText = seconds.toFixed(2).padStart(5, "0");
      return `${minutesText}:${secondsText}`;
    }

    function formatSpeaker(value) {
      if (!value) {
        return "Speaker";
      }
      const label = String(value);
      let normalized = label;
      if (label.startsWith("SPEAKER_")) {
        normalized = label.replace("SPEAKER_", "Speaker ");
      }
      normalized = normalized.replace(/_/g, " ");
      if (normalized.toLowerCase().startsWith("speaker speaker ")) {
        normalized = `Speaker ${normalized.slice("speaker speaker ".length)}`;
      }
      return normalized;
    }

    async function handleViewTranscript(item) {
      if (!item.file_key) {
        setStatus("Transcript unavailable for this session.");
        return;
      }

      try {
        setStatus("");
        const res = await fetch(`${apiBaseUrl}/transcripts/${item.file_key}`);
        if (!res.ok) {
          const errorPayload = await res.json().catch(() => ({}));
          const detail = errorPayload.detail || "Failed to load transcript";
          throw new Error(detail);
        }
        const payload = await res.json();
        const diarized = payload.diarized_segments || payload.segments || [];
        setModalContent(Array.isArray(diarized) ? diarized : []);
        setModalType("transcript");
        setModalTitle(item.title || "Session Transcript");
        setModalOpen(true);
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      }
    }

    function closeModal() {
      setModalOpen(false);
      setModalContent(null);
      setModalTitle("");
      setModalType("notes");
    }

    function toggleMenu(sessionId) {
      setOpenMenuSessionId((current) => (current === sessionId ? null : sessionId));
    }

    function formatDuration(value) {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return "—";
      }
      return `${value.toFixed(2)}s`;
    }

    function formatSessionDate(value) {
      if (!value) {
        return "—";
      }
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return "—";
      }
      return date.toLocaleDateString();
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
          "New Session"
        ),
        React.createElement(
          "button",
          {
            type: "button",
            className: view === "list" ? "secondary" : "ghost",
            onClick: () => setView("list"),
          },
          "Sessions"
        ),
        React.createElement(
          "button",
          {
            type: "button",
            className: "ghost",
            onClick: () => setTheme(theme === "dark" ? "light" : "dark"),
          },
          theme === "dark" ? "Light mode" : "Dark mode"
        )
      ),
      React.createElement(
        "section",
        { className: "card" },
        React.createElement(
          "h1",
          null,
          view === "upload" ? "Counseling Session Notes" : "Sessions"
        ),
        React.createElement(
          "p",
          { className: "subtitle" },
          view === "upload"
            ? "Upload a counseling session recording to generate a clear, structured note."
            : "Browse past sessions and their generated notes."
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
                  isUploading ? "Uploading..." : "Upload Session Audio"
                )
              ),
              React.createElement(
                "div",
                { className: "actions" },
                React.createElement(
                  "button",
                  {
                    type: "button",
                    onClick: handleProcessLarge,
                    disabled: !response || isProcessingLarge,
                    className: "ghost",
                  },
                  isProcessingLarge ? "Queueing..." : "Process Large Audio"
                )
              ),
              status
                ? React.createElement(
                    "div",
                    { className: "status" },
                    status
                  )
                : null,
              response
                ? React.createElement(
                    "pre",
                    { className: "response" },
                    JSON.stringify(response, null, 2)
                  )
                : null,
              null
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
                    React.createElement("th", null, "Session"),
                    React.createElement("th", null, "Date"),
                    React.createElement("th", null, "Status"),
                    React.createElement("th", null, "Type"),
                    React.createElement("th", null, "Duration"),
                    React.createElement("th", null, "Notes"),
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
                            item.title || `Session ${item.session_id}`
                          ),
                          React.createElement(
                            "td",
                            null,
                            formatSessionDate(item.session_date)
                          ),
                          React.createElement(
                            "td",
                            null,
                            item.status || "—"
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
                            item.notes_available ? "Yes" : "No"
                          ),
                          React.createElement(
                            "td",
                            null,
                            item.transcript_available || item.notes_available
                              ? React.createElement(
                                  "div",
                                  { className: "action-menu" },
                                  React.createElement(
                                    "button",
                                    {
                                      type: "button",
                                      className: "ghost",
                                      onClick: () =>
                                        toggleMenu(item.session_id),
                                    },
                                    "View"
                                  ),
                                  openMenuSessionId === item.session_id
                                    ? React.createElement(
                                        "div",
                                        { className: "menu-panel" },
                                        item.transcript_available
                                          ? React.createElement(
                                              "button",
                                              {
                                                type: "button",
                                                className: "ghost",
                                                onClick: () => {
                                                  handleViewTranscript(item);
                                                  setOpenMenuSessionId(null);
                                                },
                                              },
                                              "Transcript"
                                            )
                                          : null,
                                        item.notes_available
                                          ? React.createElement(
                                              "button",
                                              {
                                                type: "button",
                                                className: "ghost",
                                                onClick: () => {
                                                  handleViewNotes(item);
                                                  setOpenMenuSessionId(null);
                                                },
                                              },
                                              "Notes"
                                            )
                                          : null
                                      )
                                    : null
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
                          { colSpan: 7 },
                          "No sessions available yet."
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
        view === "list" && status
          ? React.createElement(
              "div",
              { className: "status" },
              status
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
                  React.createElement("h2", null, modalTitle || "Session Notes"),
                  React.createElement(
                    "button",
                    { type: "button", className: "ghost", onClick: closeModal },
                    "Close"
                  )
                ),
                React.createElement(
                  "div",
                  { className: "modal-body" },
                  modalType === "transcript"
                    ? React.createElement(
                        "div",
                        { className: "transcript-list" },
                        Array.isArray(modalContent) && modalContent.length
                          ? modalContent.map((segment, index) =>
                              React.createElement(
                                "div",
                                { className: "transcript-row", key: index },
                                React.createElement(
                                  "div",
                                  { className: "transcript-meta" },
                                  React.createElement(
                                    "div",
                                    { className: "transcript-speaker" },
                                    formatSpeaker(segment.speaker)
                                  ),
                                  React.createElement(
                                    "div",
                                    { className: "transcript-time" },
                                    `${formatTimecode(
                                      segment.timestamp?.start
                                    )} - ${formatTimecode(
                                      segment.timestamp?.end
                                    )}`
                                  )
                                ),
                                React.createElement(
                                  "div",
                                  { className: "transcript-text" },
                                  segment.text || ""
                                )
                              )
                            )
                          : React.createElement(
                              "div",
                              { className: "modal-content" },
                              "No transcript available."
                            )
                      )
                    : React.createElement(
                        "pre",
                        { className: "modal-content" },
                        modalContent || "No notes available."
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
