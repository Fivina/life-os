import { BookOpen, CheckCircle2, ClipboardList, Plus, RefreshCw } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatTile } from "../../components/StatTile";
import { api } from "../../services/api";
import type { Exam } from "../../types/api";

function hours(minutes?: number | null) {
  if (minutes == null) {
    return "--";
  }
  return `${Math.round(minutes / 60)}h`;
}

function shortDate(value?: string | null) {
  if (!value) {
    return "No date";
  }
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function riskTone(risk?: string) {
  if (risk === "infeasible" || risk === "critical") {
    return "rose";
  }
  if (risk === "high" || risk === "moderate") {
    return "amber";
  }
  return "green";
}

export function LearningPage() {
  const queryClient = useQueryClient();
  const [courseName, setCourseName] = useState("Macroeconomics");
  const [courseCode, setCourseCode] = useState("MACRO");
  const [examTitle, setExamTitle] = useState("Macroeconomics Final");
  const [examDate, setExamDate] = useState("2026-12-20T09:00");
  const [targetHours, setTargetHours] = useState("200");
  const [topicTitle, setTopicTitle] = useState("IS-LM Model");
  const [topicMinutes, setTopicMinutes] = useState("180");
  const [studyMinutes, setStudyMinutes] = useState("45");
  const [quality, setQuality] = useState("4");

  const status = useQuery({ queryKey: ["learning-status"], queryFn: api.learningStatus });
  const activeExam = status.data?.active_exam ?? status.data?.exams[0] ?? null;
  const selectedExamId = activeExam?.id ?? "";

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["learning-status"] });
    queryClient.invalidateQueries({ queryKey: ["exams"] });
    queryClient.invalidateQueries({ queryKey: ["current-plan"] });
  };

  const createCourse = useMutation({ mutationFn: api.createLearningCourse, onSuccess: invalidate });
  const createExam = useMutation({ mutationFn: api.addExam, onSuccess: invalidate });
  const addTopic = useMutation({
    mutationFn: (payload: { examId: string; title: string; estimated_required_minutes: number }) =>
      api.addLearningTopic(payload.examId, { title: payload.title, estimated_required_minutes: payload.estimated_required_minutes }),
    onSuccess: invalidate
  });
  const logSession = useMutation({
    mutationFn: (payload: { exam_id: string; duration_minutes: number; quality_rating: number; topic_id?: string | null }) =>
      api.logStudySession(payload),
    onSuccess: invalidate
  });
  const syncCandidates = useMutation({ mutationFn: api.syncLearningCandidateActions, onSuccess: invalidate });

  const learningBlock = useMemo(() => {
    const blocks = status.data?.current_learning_plan_window ?? [];
    return blocks.find((block) => !["completed", "skipped", "missed"].includes(String(block.status)));
  }, [status.data?.current_learning_plan_window]);

  function submitCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createCourse.mutate({ name: courseName, code: courseCode || null });
  }

  function submitExam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createExam.mutate({
      course_id: status.data?.courses[0]?.id ?? null,
      title: examTitle,
      exam_at: new Date(examDate).toISOString(),
      target_preparation_minutes: Math.max(1, Math.round(Number(targetHours) * 60)),
      importance: "goal_critical"
    });
  }

  function submitTopic(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedExamId) {
      return;
    }
    addTopic.mutate({ examId: selectedExamId, title: topicTitle, estimated_required_minutes: Math.max(1, Number(topicMinutes)) });
  }

  function submitStudy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedExamId) {
      return;
    }
    logSession.mutate({
      exam_id: selectedExamId,
      topic_id: activeExam?.topics[0]?.id ?? null,
      duration_minutes: Math.max(1, Number(studyMinutes)),
      quality_rating: Math.max(1, Math.min(5, Number(quality)))
    });
  }

  const trajectory = activeExam?.trajectory;

  return (
    <div className="stack">
      <section className="content-band">
        <div className="section-header">
          <h2>Learning</h2>
          <span>{trajectory?.risk ?? "setup"}</span>
        </div>
        {status.isLoading ? <p className="status-text">Loading Learning trajectory...</p> : null}
        {status.isError ? <p className="status-text error">Could not load Learning data.</p> : null}
        {activeExam ? (
          <div className="learning-hero">
            <div>
              <p className="eyebrow">{activeExam.course?.name ?? "Course"}</p>
              <h3>{activeExam.title}</h3>
              <p className="status-text">
                {shortDate(activeExam.exam_at ?? activeExam.exam_date)} · target {hours(activeExam.target_preparation_minutes)}
                {learningBlock ? ` · Today ${String(learningBlock.title)}` : ""}
              </p>
            </div>
            <div className={`risk-pill ${trajectory?.risk ?? "unknown"}`}>{trajectory?.risk ?? "No trajectory"}</div>
          </div>
        ) : (
          <p className="status-text">Create a course and exam to start tracking an academic trajectory.</p>
        )}
      </section>

      {trajectory ? (
        <section className="stat-grid" aria-label="Learning trajectory">
          <StatTile label="Readiness" value={`${trajectory.readiness_score}`} tone={riskTone(trajectory.risk)} />
          <StatTile label="Remaining" value={hours(trajectory.remaining_quality_adjusted_minutes)} tone="blue" />
          <StatTile label="Pace" value={`${Math.round(trajectory.required_daily_minutes)}m/d`} tone="amber" />
          <StatTile label="Capacity" value={hours(trajectory.future_capacity_minutes)} tone={trajectory.feasible ? "green" : "rose"} />
        </section>
      ) : null}

      {trajectory && !trajectory.feasible ? (
        <section className="content-band urgent-band">
          <div className="section-header">
            <h2>Infeasible Under Current Assumptions</h2>
            <span>{hours(trajectory.shortfall_minutes)} short</span>
          </div>
          <p className="status-text">
            Remaining preparation exceeds estimated sustainable study capacity. The target is not silently lowered and no fake capacity is created.
          </p>
        </section>
      ) : null}

      <section className="split-grid">
        <article className="content-band">
          <div className="section-header">
            <h2>Setup</h2>
            <BookOpen size={18} aria-hidden="true" />
          </div>
          <form className="compact-form" onSubmit={submitCourse}>
            <label>
              Course
              <input value={courseName} onChange={(event) => setCourseName(event.target.value)} />
            </label>
            <label>
              Code
              <input value={courseCode} onChange={(event) => setCourseCode(event.target.value)} />
            </label>
            <button className="primary-button" type="submit" disabled={createCourse.isPending}>
              <span>{createCourse.isPending ? "Saving" : "Create course"}</span>
              <Plus size={16} aria-hidden="true" />
            </button>
          </form>
          <form className="compact-form" onSubmit={submitExam}>
            <label>
              Exam
              <input value={examTitle} onChange={(event) => setExamTitle(event.target.value)} />
            </label>
            <label>
              Date
              <input type="datetime-local" value={examDate} onChange={(event) => setExamDate(event.target.value)} />
            </label>
            <label>
              Target hours
              <input value={targetHours} onChange={(event) => setTargetHours(event.target.value)} inputMode="numeric" />
            </label>
            <button className="primary-button" type="submit" disabled={createExam.isPending}>
              <span>{createExam.isPending ? "Saving" : "Create exam"}</span>
              <Plus size={16} aria-hidden="true" />
            </button>
          </form>
        </article>

        <article className="content-band">
          <div className="section-header">
            <h2 id="study-log" tabIndex={-1}>Study Log</h2>
            <ClipboardList size={18} aria-hidden="true" />
          </div>
          <form className="compact-form" onSubmit={submitTopic}>
            <label>
              Topic
              <input value={topicTitle} onChange={(event) => setTopicTitle(event.target.value)} disabled={!selectedExamId} />
            </label>
            <label>
              Required minutes
              <input value={topicMinutes} onChange={(event) => setTopicMinutes(event.target.value)} disabled={!selectedExamId} inputMode="numeric" />
            </label>
            <button className="secondary-button" type="submit" disabled={!selectedExamId || addTopic.isPending}>
              <span>Add topic</span>
              <Plus size={16} aria-hidden="true" />
            </button>
          </form>
          <form className="compact-form" onSubmit={submitStudy}>
            <label>
              Minutes studied
              <input value={studyMinutes} onChange={(event) => setStudyMinutes(event.target.value)} disabled={!selectedExamId} inputMode="numeric" />
            </label>
            <label>
              Quality 1-5
              <input value={quality} onChange={(event) => setQuality(event.target.value)} disabled={!selectedExamId} inputMode="numeric" />
            </label>
            <button className="primary-button" type="submit" disabled={!selectedExamId || logSession.isPending}>
              <span>{logSession.isPending ? "Logging" : "Log study"}</span>
              <CheckCircle2 size={16} aria-hidden="true" />
            </button>
          </form>
        </article>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2 id="study-candidates" tabIndex={-1}>Study Candidates</h2>
          <span>{status.data?.candidates.length ?? 0}</span>
        </div>
        <div className="candidate-list">
          {(status.data?.candidates ?? []).slice(0, 5).map((candidate) => (
            <article className="candidate-row" key={candidate.candidate_id}>
              <div>
                <strong>{candidate.title}</strong>
                <small>
                  {candidate.duration_minutes}m · {candidate.variant} · load {candidate.cognitive_load} · activation{" "}
                  {candidate.activation_difficulty}
                </small>
              </div>
              <span>{candidate.trajectory_value}</span>
            </article>
          ))}
          {!status.isLoading && !(status.data?.candidates.length ?? 0) ? <p className="status-text">No candidate study blocks yet.</p> : null}
        </div>
        <button className="secondary-button" type="button" onClick={() => syncCandidates.mutate()} disabled={syncCandidates.isPending}>
          <span>{syncCandidates.isPending ? "Syncing" : "Sync to planner"}</span>
          <RefreshCw size={16} aria-hidden="true" />
        </button>
        {syncCandidates.isSuccess ? <p className="status-text success">Learning actions synced to the planning pool.</p> : null}
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2 id="exams" tabIndex={-1}>Exams</h2>
          <span>{status.data?.exams.length ?? 0}</span>
        </div>
        <div className="exam-list">
          {(status.data?.exams ?? []).map((exam: Exam) => (
            <article className="candidate-row" key={exam.id}>
              <div>
                <strong>{exam.title}</strong>
                <small>
                  {exam.course?.name ?? "No course"} · {hours(exam.trajectory?.quality_adjusted_completed_minutes)} /{" "}
                  {hours(exam.target_preparation_minutes)} · readiness {exam.trajectory?.readiness_score ?? 0}
                </small>
              </div>
              <span>{exam.trajectory?.risk ?? exam.status}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
