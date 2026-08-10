# Saved articles

Local working folder for resolving a `status: fetch-failed` entry in `reading/queue.md`. Save the
article's content here as `<entry-id>.html` (or `.md`/`.txt`) — the exact `id` field from the queue
entry, not a name derived from the URL. `reading-agent.md` checks this path automatically before
attempting a fetch, for any entry it processes, whether `unread` or `fetch-failed`.

No status edit needed on the queue entry — dropping the correctly-named file here is the whole
resolution. (A `local-content:` field on the entry still works as an explicit override if the saved
copy lives somewhere else or under a different name.)

Not committed by default (`.gitignore`) — full article text is someone else's copyrighted content,
and this repo may be public. These files are meant to feed a local reading pass, not to live in git
history permanently. If you want a specific saved copy available to the *scheduled* reading agent
(which clones fresh from GitHub, not from this working directory), you'd need to consciously commit
and push that one file — worth thinking about before doing it, not a default.
