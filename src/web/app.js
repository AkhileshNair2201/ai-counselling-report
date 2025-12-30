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
        setTranscript(payload.transcript || "");
        setStatus("Transcription complete.");
      } catch (error) {
        setStatus(error.message || "Something went wrong.");
      } finally {
        setIsTranscribing(false);
      }
    }

    return React.createElement(
      "main",
      { className: "page" },
      React.createElement(
        "section",
        { className: "card" },
        React.createElement("h1", null, "Audio Upload"),
        React.createElement(
          "p",
          { className: "subtitle" },
          "Send an audio file to the FastAPI /upload endpoint."
        ),
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
        React.createElement(
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
      )
    );
  }

  const root = ReactDOM.createRoot(document.getElementById("root"));
  root.render(React.createElement(App));
})();
