"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

type AnalysisResponse = {
  job_id: string;
  status: string;
  input_video_name: string;
  output_video_name: string;
  output_video_path: string;
  output_video_url: string;
  frame_count: number;
  passes_team_1: number;
  passes_team_2: number;
  steals_team_1: number;
  steals_team_2: number;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Choose a basketball video to annotate.");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function checkBackendHealth() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/health`);
        if (!isMounted) {
          return;
        }

        setIsBackendConnected(response.ok);
      } catch {
        if (!isMounted) {
          return;
        }

        setIsBackendConnected(false);
      }
    }

    void checkBackendHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  const outputVideoUrl = useMemo(() => {
    if (!result) {
      return null;
    }

    return `${API_BASE_URL}${result.output_video_url}`;
  }, [result]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setResult(null);
    setErrorMessage(null);

    if (file) {
      setStatusMessage(`Ready to analyze ${file.name}.`);
    } else {
      setStatusMessage("Choose a basketball video to annotate.");
    }
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
    setErrorMessage(null);
    setResult(null);
    setStatusMessage("Uploading video and waiting for backend analysis...");

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_BASE_URL}/api/v1/analyze/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "Analysis request failed.");
      }

      setResult(data as AnalysisResponse);
      setStatusMessage("Analysis complete. Your annotated video is ready.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Something went wrong.";
      setErrorMessage(message);
      setStatusMessage("Analysis failed.");
    } finally {
      setIsSubmitting(false);
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
                  Upload a game clip, run the annotation pipeline, and watch the analyzed result.
                </h1>
                <p className="max-w-2xl text-base leading-7 text-[var(--ink-soft)] sm:text-lg">
                  This frontend sends your input video to the backend analysis endpoint, waits for
                  the tactical annotation pipeline to finish, and then displays the generated output
                  video here.
                </p>
              </div>

              <form
                onSubmit={handleSubmit}
                className="space-y-4 rounded-[1.5rem] border border-[var(--line)] bg-[var(--surface-strong)] p-5"
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

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex items-center justify-center rounded-full bg-[var(--accent)] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[var(--accent-deep)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSubmitting ? "Analyzing..." : "Upload And Analyze"}
                  </button>
                  <p className="text-sm text-[var(--ink-soft)]">{statusMessage}</p>
                </div>

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
                <p className="mt-3 text-2xl font-semibold">Player, ball, court, tactical view</p>
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
                  The annotated output video will appear here after the backend finishes processing.
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
                  <SummaryRow label="Input" value={result.input_video_name} />
                  <SummaryRow label="Output" value={result.output_video_name} />
                  <SummaryRow label="Frames" value={String(result.frame_count)} />
                  <SummaryRow label="Team 1 Passes" value={String(result.passes_team_1)} />
                  <SummaryRow label="Team 2 Passes" value={String(result.passes_team_2)} />
                  <SummaryRow label="Team 1 Steals" value={String(result.steals_team_1)} />
                  <SummaryRow label="Team 2 Steals" value={String(result.steals_team_2)} />
                </>
              ) : (
                <p className="leading-7 text-[var(--ink-soft)]">
                  Upload a video and this panel will show the completed analysis metadata from the
                  FastAPI response.
                </p>
              )}
            </div>
          </aside>
        </section>
      </div>
    </main>
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
