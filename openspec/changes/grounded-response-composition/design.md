## Decisions

### D1. Hearsay remains a generic speech host
Hearsay owns audio capture, source-tagged transcription events, session behavior, and its public integration surface. Interview question interpretation, retrieval, response generation, and teleprompter behavior remain consumer-owned. This change requires no Hearsay feature or private-Hearsay coupling.

### D2. Introduce a response coordinator between retrieval and presentation
A response coordinator owns the decision about what assistance to present for an interviewer turn. Its response package carries the query generation, selected mode, speech-ready content when present, supporting cues, evidence references, truth/experience status, provenance, and composition confidence.

Supported modes are:

- `generated-script`: a concise speech-ready response grounded in retrieved evidence;
- `cue-only`: supporting points without a full scripted response;
- `clarification`: a suggested clarification when the question or evidence is ambiguous;
- `unavailable`: an explicit no-match/failure state.

Prepared material remains valid teleprompter content and may be selected manually or by a future prepared-response selector, but automatic prepared-response matching is not introduced by this change.

### D3. Generation is gated by evidence quality
Generated scripts are allowed only when the evidence set is sufficiently relevant and internally usable for the detected question. Composition may reorganize or summarize retrieved facts, but it must not invent projects, responsibilities, metrics, technologies, outcomes, or experience status. Hypothetical/design material must remain distinguishable from implemented experience.

When the evidence is incomplete, conflicting, ambiguous, or absent, the coordinator degrades to cue-only, clarification, or unavailable behavior instead of manufacturing a polished answer.

### D4. The teleprompter is a spoken-response presentation engine
The teleprompter accepts an active content document regardless of whether its origin is prepared or generated. Generated content is ephemeral by default and carries the originating query generation and provenance references. Speech alignment operates against the active document, not against the retrieval model that created it.

### D5. New responses are staged safely
A new Remote interviewer turn may produce a pending response package, but it must not replace the active teleprompter document while the user is already answering. Activation occurs when the response surface is idle, when configured safe-auto-activation criteria are met, or when the user explicitly activates the pending response. Manual control always wins.

### D6. Supporting cues remain independently useful
A generated script may be accompanied by a small set of supporting cues such as metrics, examples, caveats, or reminders. Cues and alignment retain separate identities and update paths even when they are rendered together. Cue-only operation and teleprompter-only operation remain supported.

### D7. Local speech alignment uses a provider boundary
Only Local user speech can advance teleprompter alignment. The alignment layer consumes a consumer-facing Local speech signal interface so the implementation may use Hearsay `Local` transcript events or a consumer-owned ultra-low-latency recognizer if finalized Whisper events are not responsive enough. Remote speech never drives alignment.

TalkPrompter is the behavioral reference for pause-on-pause, off-script waiting, recovery, backward/forward rejoin, and near-camera presentation. Its MIT-licensed implementation may inform or be ported into the Python application where useful, with required license/notice preservation for any copied code; it is not a required runtime dependency.

### D8. Query generations cancel stale composition
Response composition is generation-bound just like retrieval. A superseded interviewer turn cannot activate an older generated script or overwrite newer pending guidance.

### D9. Generated responses are not persisted by default
Generated scripts and their transient evidence package remain session data unless the user explicitly saves them. This avoids silently turning interview transcripts or personal knowledge into durable artifacts.
