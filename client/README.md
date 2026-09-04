# PolicyKit website

This folder contains the pages that a user sees.

Recruiters can:

- Submit a job post for review
- Watch the review progress
- Read findings and quoted problem text
- Approve or reject suggested changes
- Record a post as published inside PolicyKit after all checks pass

Policy managers can:

- View the rule list
- Search for a rule
- Create and test a draft rule
- Publish a new rule version
- See whether the rule is ready for searches that match similar meanings

## Run the website

Follow the main [PolicyKit setup guide](../README.md) first. Then:

1. Copy `.env.local.example` to `.env.local`. This file tells the website where to find
   the Python server.
2. Start the Python server at `http://localhost:8000` as shown in the main guide.
3. Run:

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
