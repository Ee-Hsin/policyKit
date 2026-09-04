# PolicyKit website

This folder contains the Next.js website for recruiters and policy managers.

Recruiters can:

- Start from short role ideas or paste an existing job posting.
- Edit and save the posting as a series of fixed versions.
- Load older text without deleting version history.
- Recover unsaved text after an accidental browser navigation or refresh.
- Ask for optional writing help and preview the result before using it.
- Get a clear error instead of a false preview when the model returns unchanged text.
- Select **Check latest draft** to start the full compliance agent.
- See whether the last check is never run, running, current, or stale.
- Read policy findings, quoted evidence, and agent activity.
- Approve or reject model-proposed compliance text.
- Record a posting as published inside PolicyKit after all checks pass.

Policy managers can:

- View and search the policy library.
- Create and test a draft policy.
- Publish a new fixed policy version.
- See whether a policy is available to Chroma meaning-based search.

Typing, saving, viewing, loading history, accepting a preview into the editor, and
discarding a preview do not call OpenAI. Generating a first draft, requesting writing
help, and starting the full compliance agent do call OpenAI. Selected writing help sends
the selection and up to 1,500 characters from each side as context. Full-draft writing
help sends up to 12,000 characters. The compliance checker receives the complete saved
posting and every applicable policy.

Model text is never accepted automatically. The recruiter controls saved text and final
publication. Publication in this prototype only updates PolicyKit; it does not send the
posting to a job board.

An old browser or reviewer tab cannot save, approve, reject, or publish a newer version
that it did not load. If a policy reviewer rejects a posting, the recruiter must edit and
save a new version before checking again.

## Run the website

Follow the main [PolicyKit setup guide](../README.md) first. Then:

1. Copy `.env.local.example` to `.env.local`. This setting tells the website where to find
   the FastAPI server.
2. Start the Python server at `http://localhost:8000` as shown in the main guide.
3. Install the website packages and start the development server:

```bash
npm install
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000).

## Check the website code

```bash
npm run typecheck
npm run build
```

There is no sign-in, rate limiting, or separation between customer accounts in this
prototype. Do not expose it to the public internet or use confidential production data.
