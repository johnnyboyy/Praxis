---
id: coding-nextjs
subject: coding
universal: false
applies-when:
  - framework: [nextjs, next]
task-kinds: [create, change]
---

principles:

- id: suspense-not-needed-for-sync-client-components
  rule: "Do not wrap a client component in Suspense on the server side when its data is synchronously available and the component manages its own loading state internally."
  condition: "When a Next.js server component passes synchronously-fetched data to a client component that already handles skeleton/loading state (e.g., via a useHydration pattern)."
  reason: "Suspense around a non-suspending client component is a no-op for loading UX, but in Next.js App Router it affects how the page is cached and restored during back navigation — producing intermittent routing anomalies where back sends the user to an unexpected page."

- id: view-transition-scope-at-page-slot-not-layout
  rule: "Apply view transition wrappers and route-keying to the page content slot ({children}) inside the layout, never to the layout element itself or any ancestor of persistent components."
  condition: "When adding route-change animations to a Next.js App Router project that has or will have persistent state (audio player, media session) mounted in a layout."
  reason: "A key prop or transition wrapper on the layout element causes React to treat it as a new instance on every navigation, unmounting and remounting any persistent components and destroying their state."

- id: server-components-for-initial-data
  rule: "Fetch data in Server Components and pass it as props to Client Components. Only move data fetching into a Client Component when the fetch depends on client-side state — user interaction, browser APIs, or post-mount events — that is unavailable at the server render boundary."
  condition: "When a Client Component needs data from an API or database on initial render, and the fetch has no dependency on browser-only state that would prevent fetching the same data on the server."
  reason: "A Client Component that fetches data via useEffect or a client-side library sends the request from the browser after mount — adding a full network round-trip after initial HTML loads. A Server Component fetches during the server render, where the data source is co-located, before any HTML reaches the browser. The round-trip is only justified when the fetch requires client state that does not exist at server render time."

- id: revalidate-tag-over-path
  rule: "Tag cached fetches with descriptive keys using the next: { tags: [...] } option and invalidate with revalidateTag. Use revalidatePath only when the entire page cache must be cleared regardless of which data it contains."
  condition: "When deciding how to invalidate Next.js cache in a Server Action or Route Handler after a mutation."
  reason: "revalidatePath clears all cached data for a given URL path — if the page fetches N queries, all N are invalidated even if only one changed. revalidateTag targets only data carrying a specific tag, leaving unrelated cached data intact. Coarse invalidation with revalidatePath degrades performance as page data complexity grows; tag-based invalidation is surgical and scales to the mutation's actual scope."

- id: server-actions-for-mutations-not-queries
  rule: "Use Server Actions exclusively for mutation operations (create, update, delete) invoked from user interactions. Use Route Handlers for operations that return arbitrary payloads, require HTTP method control, response headers, or streaming."
  condition: "When deciding whether to implement a server-side operation as a Server Action or a Route Handler in a Next.js App Router project."
  reason: "Server Actions are optimized for the mutation → revalidate cycle: they run in response to form actions or client event handlers, mutate data, and optionally call revalidateTag or revalidatePath. They have no mechanism for HTTP method control, response headers, or streaming — capabilities Route Handlers provide. Using a Server Action as a data-fetching endpoint conflates mutation and query responsibilities and bypasses the HTTP semantics and response contract that Route Handlers are designed to enforce."
