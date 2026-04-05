"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

type AnalysisJobResponse = {
  job_id: string;
  status: string;
  message?: string | null;
  input_video_name?: string | null;
  output_video_name?: string | null;
  output_video_path?: string | null;
  output_video_url?: string | null;
  frame_count?: number | null;
  passes_team_1?: number | null;
  passes_team_2?: number | null;
  steals_team_1?: number | null;
  steals_team_2?: number | null;
};

type UploadHistoryItem = {
  file_name: string;
  file_path: string;
  file_size_bytes: number;
  created_at: string;
  video_url?: string | null;
  job_id?: string | null;
  input_video_name?: string | null;
  status?: string | null;
  frame_count?: number | null;
  passes_team_1?: number | null;
  passes_team_2?: number | null;
  steals_team_1?: number | null;
  steals_team_2?: number | null;
};

type ToggleConfig = {
  key: string;
  label: string;
  description: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const drawerToggles: ToggleConfig[] = [
  { key: "player_tracks", label: "Player tracks", description: "Bounding boxes, team colors, and ball holder markers." },
  { key: "ball_tracks", label: "Ball tracks", description: "Ball detection overlay and tracked positions." },
  { key: "team_ball_control", label: "Ball control", description: "Team possession control summary panel." },
  { key: "passes_steals", label: "Passes and steals", description: "Pass and steal event counters." },
  { key: "court_keypoints", label: "Court keypoints", description: "Detected court reference points on the video." },
  { key: "tactical_view", label: "Tactical view", description: "Mini-court tactical projection overlay." },
  { key: "speed_distance", label: "Speed and distance", description: "Per-player speed and distance labels." },
];

const stubToggles: ToggleConfig[] = [
  { key: "player_tracks", label: "Player tracks stub", description: "Reuse cached player detections and tracking." },
  { key: "ball_tracks", label: "Ball tracks stub", description: "Reuse cached ball detections and interpolation inputs." },
  { key: "court_keypoints", label: "Court keypoints stub", description: "Reuse cached court keypoint detections." },
  { key: "player_assignment", label: "Player assignment stub", description: "Reuse cached CLIP team assignments." },
];

const defaultDrawerOptions = Object.fromEntries(drawerToggles.map(({ key }) => [key, true])) as Record<string, boolean>;
const defaultStubOptions = Object.fromEntries(stubToggles.map(({ key }) => [key, true])) as Record<string, boolean>;

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Choose a basketball video to annotate.");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisJobResponse | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  const [drawerOptions, setDrawerOptions] = useState<Record<string, boolean>>(defaultDrawerOptions);
  const [stubOptions, setStubOptions] = useState<Record<string, boolean>>(defaultStubOptions);
  const [uploadHistory, setUploadHistory] = useState<UploadHistoryItem[]>([]);
  const uploadAbortController = useRef<AbortController | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function checkBackendHealth() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/health`);
        if (isMounted) {
          setIsBackendConnected(response.ok);
        }
      } catch {
        if (isMounted) {
          setIsBackendConnected(false);
        }
      }
    }

    void checkBackendHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    void loadUploadHistory();
  }, []);

  useEffect(() => {
    if (!result?.job_id || !["queued", "in_progress", "cancelling"].includes(result.status)) {
      return;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/results/${result.job_id}`);
        if (!response.ok) {
          return;
        }

        const data = (await response.json()) as AnalysisJobResponse;
        setResult(data);
        setStatusMessage(data.message ?? humanizeStatus(data.status));

        if (["completed", "failed", "cancelled"].includes(data.status)) {
          setIsSubmitting(false);
          setIsCancelling(false);
          void loadUploadHistory();
        }
      } catch {
        // Keep polling until the next interval.
      }
    }, 2000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [result?.job_id, result?.status]);

  const outputVideoUrl = useMemo(() => {
    if (!result?.output_video_url || result.status !== "completed") {
      return null;
    }

    return `${API_BASE_URL}${result.output_video_url}`;
  }, [result]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setResult(null);
    setErrorMessage(null);
    setIsSubmitting(false);
    setIsCancelling(false);

    if (file) {
      setStatusMessage(`Ready to analyze ${file.name}.`);
    } else {
      setStatusMessage("Choose a basketball video to annotate.");
    }
  }

  function toggleDrawerOption(key: string) {
    setDrawerOptions((current) => ({ ...current, [key]: !current[key] }));
  }

  function toggleStubOption(key: string) {
    setStubOptions((current) => ({ ...current, [key]: !current[key] }));
  }

  function setAllDrawerOptions(value: boolean) {
    setDrawerOptions(Object.fromEntries(drawerToggles.map(({ key }) => [key, value])) as Record<string, boolean>);
  }

  function setAllStubOptions(value: boolean) {
    setStubOptions(Object.fromEntries(stubToggles.map(({ key }) => [key, value])) as Record<string, boolean>);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setErrorMessage("Select a video file first.");
      return;
    }

    const fileName = selectedFile.name.toLowerCase();
    const supported = [".mp4", ".avi", ".mov", ".mkv"];
    if (!supported.some((extension) => fileName.endsWith(extension))) {
      setErrorMessage("Please upload a video file in mp4, avi, mov, or mkv format.");
      return;
    }

    setIsSubmitting(true);
    setIsCancelling(false);
    setErrorMessage(null);
    setResult(null);
    setStatusMessage("Uploading video and starting the analysis pipeline...");

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      for (const [key, value] of Object.entries(drawerOptions)) {
        formData.append(`draw_${key}`, String(value));
      }
      for (const [key, value] of Object.entries(stubOptions)) {
        formData.append(`stub_${key}`, String(value));
      }

      const controller = new AbortController();
      uploadAbortController.current = controller;

      const response = await fetch(`${API_BASE_URL}/api/v1/analyze/upload`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      uploadAbortController.current = null;

      const data = (await response.json()) as AnalysisJobResponse | { detail?: string };

      if (!response.ok) {
        throw new Error("detail" in data ? (data.detail ?? "Analysis request failed.") : "Analysis request failed.");
      }

      setResult(data as AnalysisJobResponse);
      setStatusMessage((data as AnalysisJobResponse).message ?? "Analysis is running...");
    } catch (error) {
      uploadAbortController.current = null;

      if (error instanceof DOMException && error.name === "AbortError") {
        setStatusMessage("Upload cancelled before the pipeline started.");
        setIsSubmitting(false);
        return;
      }

      const message = error instanceof Error ? error.message : "Something went wrong.";
      setErrorMessage(message);
      setStatusMessage("Analysis failed.");
      setIsSubmitting(false);
    }
  }

  async function handleAbort() {
    if (!isSubmitting || isCancelling) {
      return;
    }

    if (uploadAbortController.current) {
      uploadAbortController.current.abort();
      uploadAbortController.current = null;
      return;
    }

    if (!result?.job_id) {
      setIsSubmitting(false);
      setStatusMessage("Nothing is currently running.");
      return;
    }

    setIsCancelling(true);
    setStatusMessage("Stopping the pipeline safely...");

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/results/${result.job_id}/cancel`, {
        method: "POST",
      });
      const data = (await response.json()) as AnalysisJobResponse | { detail?: string };

      if (!response.ok) {
        throw new Error("detail" in data ? (data.detail ?? "Cancel request failed.") : "Cancel request failed.");
      }

      setResult(data as AnalysisJobResponse);
      setStatusMessage((data as AnalysisJobResponse).message ?? "Stopping the pipeline safely...");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Cancel request failed.";
      setErrorMessage(message);
      setIsCancelling(false);
    }
  }

  async function loadUploadHistory() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/history`);
      if (!response.ok) {
        return;
      }

      const data = (await response.json()) as UploadHistoryItem[];
      setUploadHistory(data);
    } catch {
      // Leave the history section empty if the backend is unavailable.
    }
  }

  return (
    <main className="min-h-screen px-5 py-8 text-[var(--foreground)] sm:px-8 lg:px-12">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <section className="overflow-hidden rounded-[2rem] border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)] backdrop-blur">
          <div className="grid gap-8 px-6 py-8 sm:px-8 lg:grid-cols-[1.1fr_0.9fr] lg:px-10 lg:py-10">
            <div className="space-y-6">
              <div className="inline-flex items-center rounded-full border border-[rgba(127,47,25,0.14)] bg-white/60 px-4 py-1 text-xs font-semibold uppercase tracking-[0.28em] text-[var(--accent-deep)]">
                Basketball Game Analyzer
              </div>

              <div className="space-y-4">
                <h1 className="max-w-3xl text-4xl font-semibold leading-tight sm:text-5xl">
                  Upload a game clip, customize the overlays, and watch the analyzed result.
                </h1>
                <p className="max-w-2xl text-base leading-7 text-[var(--ink-soft)] sm:text-lg">
                  Choose which drawers should render on the output video, control which cached
                  stubs are reused, and review the annotated result when the backend finishes.
                </p>
              </div>

              <form
                onSubmit={handleSubmit}
                className="space-y-5 rounded-[1.5rem] border border-[var(--line)] bg-[var(--surface-strong)] p-5"
              >
                <label
                  htmlFor="video-upload"
                  className="flex cursor-pointer flex-col gap-3 rounded-[1.25rem] border border-dashed border-[rgba(127,47,25,0.25)] bg-white/70 p-5 transition hover:border-[var(--accent)]"
                >
                  <span className="text-lg font-medium">Select input video</span>
                  <span className="text-sm leading-6 text-[var(--ink-soft)]">
                    Supported formats: `.mp4`, `.avi`, `.mov`, `.mkv`
                  </span>
                  <input
                    id="video-upload"
                    type="file"
                    accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,.mp4,.avi,.mov,.mkv"
                    onChange={handleFileChange}
                    className="block text-sm text-[var(--ink-soft)] file:mr-4 file:rounded-full file:border-0 file:bg-[var(--accent)] file:px-4 file:py-2 file:font-medium file:text-white hover:file:bg-[var(--accent-deep)]"
                  />
                </label>

                <OptionGroup
                  title="Stubs"
                  subtitle="Turn cached pipeline stages on or off for this upload."
                  options={stubToggles}
                  values={stubOptions}
                  onToggle={toggleStubOption}
                  onSetAll={setAllStubOptions}
                />

                <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex items-center justify-center rounded-full bg-[var(--accent)] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[var(--accent-deep)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSubmitting ? "Running..." : "Upload And Analyze"}
                  </button>
                  <button
                    type="button"
                    onClick={handleAbort}
                    disabled={!isSubmitting || isCancelling}
                    className="inline-flex items-center justify-center rounded-full border border-[var(--line)] bg-white px-6 py-3 text-sm font-semibold text-[var(--foreground)] transition hover:border-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isCancelling ? "Stopping..." : "Abort Upload"}
                  </button>
                  <p className="text-sm text-[var(--ink-soft)]">{statusMessage}</p>
                </div>

                {isSubmitting ? (
                  <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    First-time analysis for a video may take a couple of minutes, especially when
                    the relevant stubs do not exist yet.
                  </p>
                ) : null}

                {errorMessage ? (
                  <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {errorMessage}
                  </p>
                ) : null}
              </form>
            </div>

            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
              <div className="rounded-[1.5rem] border border-[var(--line)] bg-[var(--surface-strong)] p-5">
                <p className="text-sm uppercase tracking-[0.2em] text-[var(--ink-soft)]">Pipeline</p>
                <p className="mt-3 text-2xl font-semibold">Configurable overlays and per-stage stub reuse</p>
                <div className="mt-5 space-y-4">
                  <OptionGroup
                    title="Drawers"
                    subtitle="Choose which overlays appear on the final annotated video."
                    options={drawerToggles}
                    values={drawerOptions}
                    onToggle={toggleDrawerOption}
                    onSetAll={setAllDrawerOptions}
                  />
                </div>
              </div>
              <div className="rounded-[1.5rem] border border-[var(--line)] bg-[var(--surface-strong)] p-5">
                <p className="text-sm uppercase tracking-[0.2em] text-[var(--ink-soft)]">Backend</p>
                <p className="mt-3 break-all text-base font-medium">
                  {isBackendConnected === null
                    ? "Checking backend connection..."
                    : isBackendConnected
                      ? `Connected to ${API_BASE_URL}`
                      : "Not connected to backend"}
                </p>
              </div>
              <div className="rounded-[1.5rem] border border-[var(--line)] bg-[linear-gradient(135deg,rgba(201,92,43,0.95),rgba(127,47,25,0.95))] p-5 text-white">
                <p className="text-sm uppercase tracking-[0.2em] text-white/70">Output</p>
                <p className="mt-3 text-2xl font-semibold">Annotated video ready in-browser</p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="overflow-hidden rounded-[2rem] border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)]">
            <div className="border-b border-[var(--line)] px-6 py-4">
              <h2 className="text-2xl font-semibold">Annotated Result</h2>
            </div>

            <div className="p-6">
              {outputVideoUrl ? (
                <div className="space-y-4">
                  <video
                    key={outputVideoUrl}
                    controls
                    className="aspect-video w-full rounded-[1.5rem] bg-black"
                    src={outputVideoUrl}
                  />
                  <a
                    href={outputVideoUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium"
                  >
                    Open video in new tab
                  </a>
                </div>
              ) : (
                <div className="flex aspect-video items-center justify-center rounded-[1.5rem] border border-dashed border-[rgba(127,47,25,0.25)] bg-white/50 px-6 text-center text-[var(--ink-soft)]">
                  {result?.status === "cancelled"
                    ? "The analysis was cancelled before a final video was produced."
                    : "The annotated output video will appear here after the backend finishes processing."}
                </div>
              )}
            </div>
          </div>

          <aside className="overflow-hidden rounded-[2rem] border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)]">
            <div className="border-b border-[var(--line)] px-6 py-4">
              <h2 className="text-2xl font-semibold">Run Summary</h2>
            </div>

            <div className="space-y-4 p-6">
              {result ? (
                <>
                  <SummaryRow label="Job ID" value={result.job_id} mono />
                  <SummaryRow label="Status" value={humanizeStatus(result.status)} />
                  <SummaryRow label="Message" value={result.message ?? "No status message yet."} />
                  {result.input_video_name ? <SummaryRow label="Input" value={result.input_video_name} /> : null}
                  {result.output_video_name ? <SummaryRow label="Output" value={result.output_video_name} /> : null}
                  {result.frame_count != null ? <SummaryRow label="Frames" value={String(result.frame_count)} /> : null}
                  {result.passes_team_1 != null ? <SummaryRow label="Team 1 Passes" value={String(result.passes_team_1)} /> : null}
                  {result.passes_team_2 != null ? <SummaryRow label="Team 2 Passes" value={String(result.passes_team_2)} /> : null}
                  {result.steals_team_1 != null ? <SummaryRow label="Team 1 Steals" value={String(result.steals_team_1)} /> : null}
                  {result.steals_team_2 != null ? <SummaryRow label="Team 2 Steals" value={String(result.steals_team_2)} /> : null}
                </>
              ) : (
                <p className="leading-7 text-[var(--ink-soft)]">
                  Upload a video and this panel will show the current job status, progress message,
                  and final analysis metadata from the FastAPI backend.
                </p>
              )}
            </div>
          </aside>
        </section>

        <section className="overflow-hidden rounded-[2rem] border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)]">
          <div className="border-b border-[var(--line)] px-6 py-4">
            <h2 className="text-2xl font-semibold">Upload History</h2>
          </div>

          <div className="space-y-4 p-6">
            {uploadHistory.length > 0 ? (
              uploadHistory.map((item) => (
                <details
                  key={`${item.file_name}-${item.created_at}`}
                  className="rounded-[1.25rem] border border-[var(--line)] bg-white/70"
                >
                  <summary className="group flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4">
                    <div className="min-w-0">
                      <p className="truncate text-base font-semibold">{item.file_name}</p>
                      <p className="mt-1 text-sm text-[var(--ink-soft)]">
                        {formatDate(item.created_at)} · {formatFileSize(item.file_size_bytes)}
                      </p>
                    </div>
                    <span className="inline-flex w-8 justify-center text-2xl leading-none text-[var(--ink-soft)] transition-transform group-open:rotate-180">
                      v
                    </span>
                  </summary>

                  <div className="space-y-4 border-t border-[var(--line)] px-4 py-4">
                    {item.video_url && isBrowserPlayableVideo(item.file_name) ? (
                      <div className="space-y-3">
                        <video
                          controls
                          className="aspect-video w-full rounded-[1.25rem] bg-black"
                          src={`${API_BASE_URL}${item.video_url}`}
                        />
                      </div>
                    ) : null}

                    {item.video_url && !isBrowserPlayableVideo(item.file_name) ? (
                      <p className="rounded-[1rem] border border-[var(--line)] bg-white/80 px-4 py-3 text-sm text-[var(--ink-soft)]">
                        This saved file format may not play inline in the browser. Open it in a new
                        tab or download it instead.
                      </p>
                    ) : null}

                    <div className="grid gap-3 md:grid-cols-2">
                      <SummaryRow label="Created" value={formatDate(item.created_at)} />
                      <SummaryRow label="Size" value={formatFileSize(item.file_size_bytes)} />
                      <SummaryRow label="Path" value={item.file_path} mono />
                      <SummaryRow label="Status" value={item.status ? humanizeStatus(item.status) : "Saved output"} />
                      {item.input_video_name ? <SummaryRow label="Input" value={item.input_video_name} /> : null}
                      {item.job_id ? <SummaryRow label="Job ID" value={item.job_id} mono /> : null}
                      {item.frame_count != null ? <SummaryRow label="Frames" value={String(item.frame_count)} /> : null}
                      {item.passes_team_1 != null ? <SummaryRow label="Team 1 Passes" value={String(item.passes_team_1)} /> : null}
                      {item.passes_team_2 != null ? <SummaryRow label="Team 2 Passes" value={String(item.passes_team_2)} /> : null}
                      {item.steals_team_1 != null ? <SummaryRow label="Team 1 Steals" value={String(item.steals_team_1)} /> : null}
                      {item.steals_team_2 != null ? <SummaryRow label="Team 2 Steals" value={String(item.steals_team_2)} /> : null}
                    </div>

                    {item.video_url ? (
                      <a
                        href={`${API_BASE_URL}${item.video_url}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-medium"
                      >
                        Open output video
                      </a>
                    ) : null}
                  </div>
                </details>
              ))
            ) : (
              <p className="leading-7 text-[var(--ink-soft)]">
                No processed uploads have been found in the output videos folder yet.
              </p>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function OptionGroup({
  title,
  subtitle,
  options,
  values,
  onToggle,
  onSetAll,
}: {
  title: string;
  subtitle: string;
  options: ToggleConfig[];
  values: Record<string, boolean>;
  onToggle: (key: string) => void;
  onSetAll: (value: boolean) => void;
}) {
  return (
    <section className="rounded-[1.25rem] border border-[var(--line)] bg-white/60 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-[var(--ink-soft)]">{subtitle}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => onSetAll(true)}
            className="rounded-full border border-[var(--line)] bg-transparent px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--ink-soft)] transition hover:border-[var(--accent)] hover:text-[var(--accent-deep)]"
          >
            On
          </button>
          <button
            type="button"
            onClick={() => onSetAll(false)}
            className="rounded-full border border-[var(--line)] bg-transparent px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--ink-soft)] transition hover:border-[var(--accent)] hover:text-[var(--accent-deep)]"
          >
            Off
          </button>
        </div>
      </div>
      <div className="space-y-3">
        {options.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => onToggle(option.key)}
            className={`flex w-full items-start justify-between gap-4 rounded-[1rem] border px-4 py-3 text-left transition ${
              values[option.key]
                ? "border-[var(--accent)] bg-[rgba(201,92,43,0.08)]"
                : "border-[var(--line)] bg-white/80"
            }`}
          >
            <div>
              <p className="font-medium">{option.label}</p>
              <p className="mt-1 text-sm leading-6 text-[var(--ink-soft)]">{option.description}</p>
            </div>
            <span
              className={`inline-flex min-w-16 justify-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                values[option.key]
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[rgba(31,26,22,0.08)] text-[var(--ink-soft)]"
              }`}
            >
              {values[option.key] ? "On" : "Off"}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function SummaryRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-[1.25rem] border border-[var(--line)] bg-white/70 px-4 py-3">
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--ink-soft)]">{label}</p>
      <p className={`mt-2 text-sm font-medium ${mono ? "break-all font-mono" : ""}`}>{value}</p>
    </div>
  );
}

function humanizeStatus(status: string) {
  switch (status) {
    case "queued":
      return "Queued";
    case "in_progress":
      return "In progress";
    case "cancelling":
      return "Cancelling";
    case "cancelled":
      return "Cancelled";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function isBrowserPlayableVideo(fileName: string) {
  return fileName.toLowerCase().endsWith(".mp4");
}
